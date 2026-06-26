"""Token 导出服务 — 组装 kiro-account-manager 标准 JSON."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.client import AsyncAWSClient
from app.core.config import get_settings
from app.core.exceptions import TokenExportConfigurationError
from app.core.security import decrypt
from app.repositories.account_repo import AccountRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.user_repo import ICUserRepository

logger = logging.getLogger(__name__)

# 订阅类型 → 展示名称映射
SUBSCRIPTION_DISPLAY: dict[str, tuple[str, str]] = {
    "Q_DEVELOPER_STANDALONE_POWER": ("Enterprise", "KIRO POWER"),
    "Q_DEVELOPER_STANDALONE_PRO_PLUS": ("Enterprise", "KIRO PRO PLUS"),
    "Q_DEVELOPER_STANDALONE_PRO": ("Enterprise", "KIRO PRO"),
    "KIRO_ENTERPRISE_PRO_POWER": ("Enterprise", "KIRO POWER"),
    "KIRO_ENTERPRISE_PRO_MAX": ("Enterprise", "KIRO PRO MAX"),
    "KIRO_ENTERPRISE_PRO_PLUS": ("Enterprise", "KIRO PRO PLUS"),
    "KIRO_ENTERPRISE_PRO": ("Enterprise", "KIRO PRO"),
}


class TokenExportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.user_repo = ICUserRepository(session)
        self.sub_repo = SubscriptionRepository(session)

    async def export_account_json(
        self,
        account_id: int,
        task_id: int | None = None,
        user_ids: list[int] | None = None,
    ) -> str:
        """导出指定账号的用户 JSON，写入 data/exports/，返回文件路径."""
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            from app.core.exceptions import AccountNotFoundError

            raise AccountNotFoundError(account_id)

        # 提取 domain 前缀（用于 userId 构造）
        # kiro_login_url 形如 https://d-xxxxxxxx.awsapps.com/start
        dir_id = self._extract_dir_id(account.kiro_login_url or "")

        # 拉取用户列表
        if user_ids:
            users = [
                u
                for uid in user_ids
                if (u := await self.user_repo.get_by_id(uid)) and u.aws_account_id == account_id
            ]
        else:
            users, _ = await self.user_repo.list_by_account(account_id, page_size=10000)

        entries = []
        for user in users:
            if not user.email:
                logger.warning("Skipping user %s: no email configured", user.user_name)
                continue
            sub = await self.sub_repo.get_by_principal(account_id, user.user_id)
            entry = await self._build_entry(account, user, sub, dir_id)
            entries.append(entry)

        settings = get_settings()
        os.makedirs(settings.EXPORTS_DIR, exist_ok=True)

        file_name = f"{task_id or uuid.uuid4().hex}_{account_id}.json"
        file_path = os.path.join(settings.EXPORTS_DIR, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

        logger.info("Exported %d entries to %s", len(entries), file_path)
        return file_path

    async def _build_entry(self, account, user, sub, dir_id: str) -> dict[str, Any]:
        """构建单个用户的 JSON 条目."""
        now_ms = int(time.time() * 1000)
        expires_ms = now_ms + 8 * 3600 * 1000  # +8 小时

        raw_type = sub.subscription_type if sub else "Q_DEVELOPER_STANDALONE_PRO"
        sub_type, sub_title = SUBSCRIPTION_DISPLAY.get(raw_type, ("Enterprise", "KIRO PRO"))

        # userId 格式：<dirId>.<username>
        user_id_str = f"{dir_id}.{user.user_name}" if dir_id else user.user_name
        email = user.email or f"{user.user_name}@{dir_id}.local" if dir_id else user.email or ""

        # days_remaining：订阅从创建日起算30天（保守估计）
        days_remaining = 30
        if sub and sub.start_date:
            start = sub.start_date
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - start).days
            days_remaining = max(0, 30 - elapsed)

        access_token, expires_ms = await self.get_sso_access_token(account, user.email or "")

        return {
            "email": email,
            "userId": user_id_str,
            "nickname": user.user_name,
            "idp": "Enterprise",
            "credentials": {
                "accessToken": access_token,
                "csrfToken": "",
                "refreshToken": "",
                "clientId": "",
                "clientSecret": "",
                "region": account.sso_region,
                "expiresAt": expires_ms,
                "authMethod": "IdC",
                "provider": "Enterprise",
            },
            "subscription": {
                "type": "Enterprise",
                "title": sub_title,
                "daysRemaining": days_remaining,
                "rawType": raw_type,
            },
            "usage": {"current": 0, "limit": 10000, "percentUsed": 0},
            "tags": [],
            "status": "active",
            "id": str(uuid.uuid4()),
            "machineId": "",
            "createdAt": now_ms,
            "lastCheckedAt": now_ms,
        }

    async def get_sso_access_token(self, account, user_email: str) -> tuple[str, int]:
        """为指定用户动态签发 JWT，通过 Trusted Token Issuer 换取 IdC access token."""
        settings = get_settings()
        if not settings.SSO_OIDC_CLIENT_ID or not settings.SSO_OIDC_PRIVATE_KEY_B64:
            raise TokenExportConfigurationError(
                "请配置 SSO_OIDC_CLIENT_ID 和 SSO_OIDC_PRIVATE_KEY_B64"
            )
        if not user_email:
            raise TokenExportConfigurationError("导出令牌需要用户邮箱作为 Identity Center subject")

        assertion = self._sign_jwt(
            private_key_pem=base64.b64decode(settings.SSO_OIDC_PRIVATE_KEY_B64),
            issuer=settings.SSO_OIDC_ISSUER_URL,
            audience=settings.SSO_OIDC_AUDIENCE,
            email=user_email,
            kid=settings.SSO_OIDC_KEY_ID,
        )

        client = AsyncAWSClient(
            decrypt(account.access_key_id),
            decrypt(account.secret_access_key),
            account.sso_region,
        )
        response = await client.boto3_call(
            "sso-oidc",
            "create_token_with_iam",
            region=account.sso_region,
            clientId=settings.SSO_OIDC_CLIENT_ID,
            grantType="urn:ietf:params:oauth:grant-type:jwt-bearer",
            assertion=assertion,
            requestedTokenType=settings.SSO_OIDC_REQUESTED_TOKEN_TYPE,
        )
        token = response.get("accessToken")
        if not token:
            raise TokenExportConfigurationError("CreateTokenWithIAM 未返回 accessToken")
        expires_in = int(response.get("expiresIn", 8 * 3600))
        return token, int(time.time() * 1000) + expires_in * 1000

    @staticmethod
    def _sign_jwt(
        private_key_pem: bytes,
        issuer: str,
        audience: str,
        email: str,
        kid: str,
    ) -> str:
        """用 RSA 私钥为指定用户签发 JWT assertion."""
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        priv = load_pem_private_key(private_key_pem, password=None)
        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT", "kid": kid}
        payload = {
            "iss": issuer,
            "sub": email,
            "email": email,
            "aud": audience,
            "iat": now,
            "exp": now + 3600,
            "jti": uuid.uuid4().hex,
        }

        def b64url(data: dict | bytes) -> str:
            if isinstance(data, dict):
                data = json.dumps(data, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        msg = f"{b64url(header)}.{b64url(payload)}".encode()
        sig = priv.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        return f"{msg.decode()}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"

    @staticmethod
    def _extract_dir_id(login_url: str) -> str:
        """从 SSO 登录 URL 提取 directory ID 前缀（如 d-1234abcd）."""
        if not login_url:
            return ""
        try:
            # URL 形如 https://d-xxxxxxxx.awsapps.com/start
            host = login_url.split("//")[-1].split("/")[0]
            dir_id = host.split(".")[0]
            return dir_id
        except Exception:
            return ""
