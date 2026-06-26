"""订阅业务逻辑."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.kiro import KiroSubscriptionClient
from app.core.exceptions import (
    AccountNotFoundError,
    AccountNotVerifiedError,
    SubscriptionNotFoundError,
    UserNotFoundError,
)
from app.core.security import decrypt
from app.repositories.account_repo import AccountRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.user_repo import ICUserRepository
from app.services.log_service import LogService

logger = logging.getLogger(__name__)


def _get_kiro_client(account) -> KiroSubscriptionClient:
    from app.aws.client import AsyncAWSClient

    ak = decrypt(account.access_key_id)
    sk = decrypt(account.secret_access_key)
    aws_client = AsyncAWSClient(ak, sk, account.sso_region)
    return KiroSubscriptionClient(aws_client, account.kiro_region, account.sso_region)


class SubscriptionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.account_repo = AccountRepository(session)
        self.user_repo = ICUserRepository(session)
        self.sub_repo = SubscriptionRepository(session)
        self.log_svc = LogService(session)

    async def _require_account(self, account_id: int):
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        if account.status != "active":
            raise AccountNotVerifiedError()
        return account

    async def assign(
        self,
        account_id: int,
        ic_user_id: int,
        subscription_type: str,
        operator: str | None = None,
    ):
        """分配订阅给 IC 用户."""
        account = await self._require_account(account_id)
        user = await self.user_repo.get_by_id(ic_user_id)
        if not user or user.aws_account_id != account_id:
            raise UserNotFoundError(ic_user_id)

        kiro_client = _get_kiro_client(account)
        try:
            await kiro_client.create_assignment(
                instance_arn=account.instance_arn,
                principal_id=user.user_id,
                subscription_type=subscription_type,
            )
        except Exception as e:
            # 失败写入 pending，等 scheduler 重试
            await self.user_repo.update(user, pending_subscription_type=subscription_type)
            await self.log_svc.log(
                operation="assign_subscription",
                status="failed",
                account_id=account_id,
                target=f"{user.user_name}:{subscription_type}",
                message=str(e),
                operator=operator,
            )
            raise

        # 成功则清除 pending，写入订阅记录
        await self.user_repo.update(user, pending_subscription_type=None)

        existing = await self.sub_repo.get_by_principal(account_id, user.user_id)
        if existing:
            sub = await self.sub_repo.update(
                existing,
                subscription_type=subscription_type,
                status="active",
                last_synced=datetime.now(timezone.utc),
            )
        else:
            sub = await self.sub_repo.create(
                aws_account_id=account_id,
                user_id=ic_user_id,
                principal_id=user.user_id,
                subscription_type=subscription_type,
                status="active",
                start_date=datetime.now(timezone.utc),
            )

        await self.log_svc.log(
            operation="assign_subscription",
            status="success",
            account_id=account_id,
            target=f"{user.user_name}:{subscription_type}",
            operator=operator,
        )
        return sub

    async def cancel(self, account_id: int, sub_id: int, operator: str | None = None) -> None:
        account = await self._require_account(account_id)
        sub = await self.sub_repo.get_by_id(sub_id)
        if not sub or sub.aws_account_id != account_id:
            raise SubscriptionNotFoundError(sub_id)

        kiro_client = _get_kiro_client(account)
        try:
            await kiro_client.delete_assignment(
                instance_arn=account.instance_arn,
                principal_id=sub.principal_id,
            )
        except Exception as e:
            await self.log_svc.log(
                operation="cancel_subscription",
                status="failed",
                account_id=account_id,
                target=sub.principal_id,
                message=str(e),
                operator=operator,
            )
            raise

        await self.sub_repo.update(sub, status="canceled")
        await self.log_svc.log(
            operation="cancel_subscription",
            status="success",
            account_id=account_id,
            target=sub.principal_id,
            operator=operator,
        )

    async def change_plan(
        self,
        account_id: int,
        sub_id: int,
        new_type: str,
        operator: str | None = None,
    ):
        account = await self._require_account(account_id)
        sub = await self.sub_repo.get_by_id(sub_id)
        if not sub or sub.aws_account_id != account_id:
            raise SubscriptionNotFoundError(sub_id)

        kiro_client = _get_kiro_client(account)
        await kiro_client.update_assignment(
            instance_arn=account.instance_arn,
            principal_id=sub.principal_id,
            subscription_type=new_type,
        )
        sub = await self.sub_repo.update(sub, subscription_type=new_type)
        await self.log_svc.log(
            operation="change_plan",
            status="success",
            account_id=account_id,
            target=f"{sub.principal_id}:{new_type}",
            operator=operator,
        )
        return sub

    async def bulk_change_plan(
        self,
        account_id: int,
        sub_ids: list[int],
        new_type: str,
        operator: str | None = None,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {"success": [], "failed": []}
        for sub_id in sub_ids:
            try:
                await self.change_plan(account_id, sub_id, new_type, operator)
                results["success"].append(sub_id)
            except Exception as e:
                results["failed"].append({"id": sub_id, "error": str(e)})
        return results

    async def list_by_account(
        self, account_id: int, status: str | None = None, page: int = 1, page_size: int = 50
    ) -> tuple[list, int]:
        account = await self.account_repo.get_by_id(account_id)
        if not account:
            raise AccountNotFoundError(account_id)
        return await self.sub_repo.list_by_account(account_id, status, page, page_size)

    async def list_all(
        self, status: str | None = None, page: int = 1, page_size: int = 50
    ) -> tuple[list, int]:
        """跨账号订阅总览."""
        return await self.sub_repo.list_all(status, page, page_size)

    async def list_canceled(
        self, account_id: int | None = None, page: int = 1, page_size: int = 50
    ) -> tuple[list, int]:
        return await self.sub_repo.list_canceled(account_id, page, page_size)
