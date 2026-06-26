"""同步服务 — 将 AWS 数据同步到本地 DB."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.identity_center import IdentityCenterClient
from app.aws.kiro import KiroSubscriptionClient
from app.core.security import decrypt
from app.repositories.account_repo import AccountRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.user_repo import ICUserRepository
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


def _get_clients(account):
    from app.aws.client import AsyncAWSClient

    ak = decrypt(account.access_key_id)
    sk = decrypt(account.secret_access_key)
    aws_client = AsyncAWSClient(ak, sk, account.sso_region)
    ic_client = IdentityCenterClient(aws_client, account.sso_region, account.identity_store_id)
    kiro_client = KiroSubscriptionClient(aws_client, account.kiro_region, account.sso_region)
    return ic_client, kiro_client


class SyncService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.user_repo = ICUserRepository(session)
        self.sub_repo = SubscriptionRepository(session)
        self.log_svc = LogService(session)

    async def sync_account(self, account_id: int) -> dict[str, Any]:
        """同步指定账号的 IC 用户和订阅."""
        account = await self.account_repo.get_by_id(account_id)
        if not account or account.status != "active":
            return {"skipped": True, "reason": "account not active"}

        logger.info("Syncing account %d (%s)", account_id, account.name)
        result: dict[str, Any] = {}

        try:
            ic_client, kiro_client = _get_clients(account)

            # 同步用户
            user_result = await self._sync_users(account, ic_client)
            result["users"] = user_result

            # 同步订阅
            sub_result = await self._sync_subscriptions(account, kiro_client)
            result["subscriptions"] = sub_result

            # 更新 last_synced
            from sqlalchemy import update

            from app.models.aws_account import AWSAccount

            stmt = (
                update(AWSAccount)
                .where(AWSAccount.id == account_id)
                .values(last_synced=datetime.now(timezone.utc))
            )
            await self.session.execute(stmt)

            await self.log_svc.log(
                operation="sync_account",
                status="success",
                account_id=account_id,
                message=f"同步完成: 用户 {user_result}, 订阅 {sub_result}",
            )
        except Exception as e:
            logger.error("Sync failed for account %d: %s", account_id, e)
            await self.log_svc.log(
                operation="sync_account",
                status="failed",
                account_id=account_id,
                message=str(e),
            )
            result["error"] = str(e)

        return result

    async def sync_all_accounts(self) -> list[dict[str, Any]]:
        """同步所有 active 账号."""
        accounts = await self.account_repo.list_all()
        results = []
        for account in accounts:
            if account.status == "active":
                r = await self.sync_account(account.id)
                r["account_id"] = account.id
                results.append(r)
        return results

    async def _sync_users(self, account, ic_client: IdentityCenterClient) -> dict:
        """从 AWS 同步用户列表到本地."""
        remote_users = await ic_client.list_all_users()
        created = updated = 0

        for ru in remote_users:
            aws_uid = ru.get("UserId", "")
            emails = ru.get("Emails", [])
            email = next((e["Value"] for e in emails if e.get("Primary")), None)
            name_obj = ru.get("Name", {})

            existing = await self.user_repo.get_by_aws_user_id(account.id, aws_uid)
            if existing:
                await self.user_repo.update(
                    existing,
                    user_name=ru.get("UserName", existing.user_name),
                    display_name=ru.get("DisplayName", existing.display_name),
                    email=email or existing.email,
                    given_name=name_obj.get("GivenName", existing.given_name),
                    family_name=name_obj.get("FamilyName", existing.family_name),
                    last_synced=datetime.now(timezone.utc),
                )
                updated += 1
            else:
                await self.user_repo.create(
                    aws_account_id=account.id,
                    user_id=aws_uid,
                    user_name=ru.get("UserName", ""),
                    display_name=ru.get("DisplayName"),
                    email=email,
                    given_name=name_obj.get("GivenName"),
                    family_name=name_obj.get("FamilyName"),
                    status="active",
                    last_synced=datetime.now(timezone.utc),
                )
                created += 1

        return {"created": created, "updated": updated, "total": len(remote_users)}

    async def _sync_subscriptions(self, account, kiro_client: KiroSubscriptionClient) -> dict:
        """从 AWS 同步订阅状态到本地."""
        remote_subs = await kiro_client.list_all_user_subscriptions(account.instance_arn)
        synced = 0

        for rs in remote_subs:
            principal_id = rs.get("PrincipalId", "")
            sub_type = rs.get("SubscriptionType", "")
            status = rs.get("Status", "active").lower()

            existing = await self.sub_repo.get_by_principal(account.id, principal_id)
            if existing:
                await self.sub_repo.update(
                    existing,
                    subscription_type=sub_type,
                    status=status,
                    last_synced=datetime.now(timezone.utc),
                )
            else:
                # 尝试通过 principal_id 找到对应的 IC 用户
                user = await self.user_repo.get_by_aws_user_id(account.id, principal_id)
                await self.sub_repo.create(
                    aws_account_id=account.id,
                    user_id=user.id if user else None,
                    principal_id=principal_id,
                    subscription_type=sub_type,
                    status=status,
                    last_synced=datetime.now(timezone.utc),
                )
            synced += 1

        return {"synced": synced}

    async def retry_pending_subscriptions(self) -> dict[str, Any]:
        """重试所有 pending_subscription_type 的用户."""
        pending_users = await self.user_repo.list_with_pending_subscription()
        success = failed = 0

        for user in pending_users:
            account = await self.account_repo.get_by_id(user.aws_account_id)
            if not account or account.status != "active":
                continue

            sub_type = user.pending_subscription_type
            try:
                from app.services.subscription_service import SubscriptionService

                sub_svc = SubscriptionService(self.session)
                await sub_svc.assign(
                    account_id=account.id,
                    ic_user_id=user.id,
                    subscription_type=sub_type,
                    operator="scheduler",
                )
                success += 1
            except Exception as e:
                logger.warning("Retry failed for user %d (type=%s): %s", user.id, sub_type, e)
                failed += 1

        return {"success": success, "failed": failed}
