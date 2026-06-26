"""Credit 用量统计业务逻辑."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.kiro import KiroSubscriptionClient
from app.core.exceptions import AccountNotFoundError, AccountNotVerifiedError
from app.core.security import decrypt
from app.repositories.account_repo import AccountRepository
from app.repositories.subscription_repo import CreditUsageRepository
from app.repositories.user_repo import ICUserRepository
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


class CreditService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.user_repo = ICUserRepository(session)
        self.credit_repo = CreditUsageRepository(session)
        self.log_svc = LogService(session)

    async def sync_credits(self, account_id: int) -> dict[str, Any]:
        """从 ListUserSubscriptions 提取 usage 字段并保存到 credit_usage."""
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        if account.status != "active":
            raise AccountNotVerifiedError()

        from app.aws.client import AsyncAWSClient

        ak = decrypt(account.access_key_id)
        sk = decrypt(account.secret_access_key)
        aws_client = AsyncAWSClient(ak, sk, account.sso_region)
        kiro_client = KiroSubscriptionClient(aws_client, account.kiro_region, account.sso_region)

        remote_subs = await kiro_client.list_all_user_subscriptions(account.instance_arn)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        synced = 0

        for rs in remote_subs:
            principal_id = rs.get("PrincipalId", "")
            usage = rs.get("Usage", {})
            if not usage:
                continue

            total_credits = usage.get("Total", 0)
            breakdown = usage.get("FeatureBreakdown", {})

            # 找到对应的本地用户
            user = await self.user_repo.get_by_aws_user_id(account_id, principal_id)
            if not user:
                continue

            await self.credit_repo.upsert(
                user_id=user.id,
                date=today,
                total_credits=total_credits,
                breakdown=breakdown,
            )
            synced += 1

        await self.log_svc.log(
            operation="sync_credits",
            status="success",
            account_id=account_id,
            message=f"同步 Credit 用量 {synced} 条",
        )
        return {"synced": synced, "date": today}

    async def list_credits(
        self,
        account_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list, int]:
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return await self.credit_repo.list_by_account(
            account_id, start_date, end_date, page, page_size
        )

    async def list_user_credits(
        self,
        user_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list:
        return await self.credit_repo.list_by_user(user_id, start_date, end_date)
