"""认证 & 系统用户业务逻辑."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    DuplicateEmailError,
    DuplicateUsernameError,
    InvalidTokenError,
    LastAdminError,
    MFAChallengeRequired,
    MFACodeInvalidError,
    SystemUserNotFoundError,
)
from app.core.security import (
    create_access_token,
    create_pre_auth_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    verify_password,
    verify_totp,
)
from app.repositories.user_repo import SystemUserRepository

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SystemUserRepository(session)

    async def login(self, username: str, password: str) -> dict:
        """第一步登录。
        - 如未启用 MFA：直接返回 access_token + refresh_token
        - 如已启用 MFA：抛出 MFAChallengeRequired（含 pre_auth_token）
        """
        user = await self.repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("用户名或密码错误")
        if not user.is_active:
            raise AuthenticationError("账号已被禁用")

        if user.mfa_enabled and user.totp_secret:
            pre_auth_token = create_pre_auth_token(user.id)
            raise MFAChallengeRequired(pre_auth_token)

        return await self._issue_tokens(user)

    async def verify_mfa(self, pre_auth_token: str, totp_code: str) -> dict:
        """MFA 第二步验证。必须携带 pre_auth_token（type=mfa_challenge）."""
        try:
            payload = decode_token(pre_auth_token, expected_type="mfa_challenge")
        except JWTError as e:
            raise InvalidTokenError(f"pre_auth_token 无效: {e}") from e

        user_id = int(payload["sub"])
        user = await self.repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise InvalidTokenError("用户不存在或已被禁用")

        if not user.totp_secret or not verify_totp(user.totp_secret, totp_code):
            raise MFACodeInvalidError("MFA 验证码无效")

        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> dict:
        """刷新 access_token。查库验证用户存在且 is_active."""
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except JWTError as e:
            raise InvalidTokenError(f"refresh_token 无效: {e}") from e

        # 查库验证 token 状态
        rt_record = await self.repo.get_refresh_token(refresh_token)
        if not rt_record or rt_record.revoked:
            raise InvalidTokenError("refresh_token 已吊销")

        now = datetime.now(timezone.utc)
        if rt_record.expires_at.replace(tzinfo=timezone.utc) < now:
            raise InvalidTokenError("refresh_token 已过期")

        user = await self.repo.get_by_id(int(payload["sub"]))
        if not user or not user.is_active:
            raise InvalidTokenError("用户不存在或已被禁用")

        # 吊销旧 token，签发新 token
        await self.repo.revoke_refresh_token(refresh_token)
        return await self._issue_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        """吊销 refresh_token."""
        await self.repo.revoke_refresh_token(refresh_token)

    async def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise SystemUserNotFoundError(user_id)
        if not verify_password(old_password, user.hashed_password):
            raise AuthenticationError("旧密码错误")
        await self.repo.update(user, hashed_password=hash_password(new_password))
        await self.repo.revoke_all_user_tokens(user_id)

    # ── MFA 管理 ──────────────────────────────────────────────────────────

    async def setup_mfa(self, user_id: int) -> dict:
        """生成 TOTP secret，不立即启用（需 enable_mfa 确认）."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise SystemUserNotFoundError(user_id)
        secret = generate_totp_secret()
        await self.repo.update(user, totp_secret=secret)
        uri = get_totp_uri(secret, user.username)
        return {"secret": secret, "uri": uri}

    async def enable_mfa(self, user_id: int, totp_code: str) -> None:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise SystemUserNotFoundError(user_id)
        if not user.totp_secret or not verify_totp(user.totp_secret, totp_code):
            raise MFACodeInvalidError("验证码无效，无法启用 MFA")
        await self.repo.update(user, mfa_enabled=True)

    async def disable_mfa(self, user_id: int, totp_code: str) -> None:
        """禁用 MFA，需先验证当前 TOTP code."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise SystemUserNotFoundError(user_id)
        if not user.totp_secret or not verify_totp(user.totp_secret, totp_code):
            raise MFACodeInvalidError("验证码无效，无法禁用 MFA")
        await self.repo.update(user, mfa_enabled=False, totp_secret=None)

    # ── 系统用户管理 ──────────────────────────────────────────────────────

    async def create_system_user(
        self,
        username: str,
        email: str,
        password: str,
        is_admin: bool = False,
        operator: str = "system",
    ):
        # 检查重复
        if await self.repo.get_by_username(username):
            raise DuplicateUsernameError(username)
        if await self.repo.get_by_email(email):
            raise DuplicateEmailError(email)

        return await self.repo.create(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            is_admin=is_admin,
        )

    async def get_system_user(self, user_id: int):
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise SystemUserNotFoundError(user_id)
        return user

    async def list_system_users(self):
        return await self.repo.list_all()

    async def update_system_user(self, user_id: int, **kwargs):
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise SystemUserNotFoundError(user_id)
        return await self.repo.update(user, **kwargs)

    async def delete_system_user(self, user_id: int) -> None:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise SystemUserNotFoundError(user_id)
        if user.is_admin:
            admin_count = await self.repo.count_admins()
            if admin_count <= 1:
                raise LastAdminError()
        await self.repo.revoke_all_user_tokens(user_id)
        await self.repo.delete(user)

    async def admin_reset_password(self, user_id: int, new_password: str) -> None:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise SystemUserNotFoundError(user_id)
        await self.repo.update(user, hashed_password=hash_password(new_password))
        await self.repo.revoke_all_user_tokens(user_id)

    # ── 内部辅助 ──────────────────────────────────────────────────────────

    async def _issue_tokens(self, user) -> dict:
        from app.core.config import get_settings

        settings = get_settings()

        access_token = create_access_token(
            subject=user.id,
            extra={"username": user.username, "is_admin": user.is_admin},
        )
        refresh_token = create_refresh_token(subject=user.id)

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.repo.create_refresh_token(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at,
        )
        return {"access_token": access_token, "refresh_token": refresh_token}

    async def get_current_user(self, token: str):
        """从 access_token 中取用户（给依赖注入用）."""
        try:
            payload = decode_token(token, expected_type="access")
        except JWTError as e:
            raise InvalidTokenError(str(e)) from e
        user = await self.repo.get_by_id(int(payload["sub"]))
        if not user or not user.is_active:
            raise InvalidTokenError("用户不存在或已被禁用")
        return user

    async def ensure_initial_admin(self) -> None:
        """首次启动时确保存在管理员用户."""
        from app.core.config import get_settings

        settings = get_settings()
        existing = await self.repo.get_by_username(settings.INITIAL_ADMIN_USERNAME)
        if not existing:
            await self.create_system_user(
                username=settings.INITIAL_ADMIN_USERNAME,
                email=settings.INITIAL_ADMIN_EMAIL,
                password=settings.INITIAL_ADMIN_PASSWORD,
                is_admin=True,
            )
            logger.info("Initial admin user created: %s", settings.INITIAL_ADMIN_USERNAME)
