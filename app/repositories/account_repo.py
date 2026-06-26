"""账号数据访问层."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aws_account import AWSAccount, ICUser, KiroSubscription


class AccountRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, account_id: int) -> AWSAccount | None:
        result = await self.session.get(AWSAccount, account_id)
        return result

    async def get_by_name(self, name: str) -> AWSAccount | None:
        stmt = select(AWSAccount).where(AWSAccount.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[AWSAccount]:
        stmt = select(AWSAccount).order_by(AWSAccount.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> AWSAccount:
        account = AWSAccount(**kwargs)
        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def update(self, account: AWSAccount, **kwargs: Any) -> AWSAccount:
        for key, value in kwargs.items():
            if value is not None or key in ("description", "kiro_login_url"):
                setattr(account, key, value)
        await self.session.flush()
        await self.session.refresh(account)
        return account

    async def delete(self, account: AWSAccount) -> None:
        await self.session.delete(account)
        await self.session.flush()

    async def set_status(
        self, account_id: int, status: str, last_verified: datetime | None = None
    ) -> None:
        values: dict[str, Any] = {"status": status}
        if last_verified is not None:
            values["last_verified"] = last_verified
        stmt = update(AWSAccount).where(AWSAccount.id == account_id).values(**values)
        await self.session.execute(stmt)

    async def clear_default(self) -> None:
        stmt = update(AWSAccount).values(is_default=False)
        await self.session.execute(stmt)

    async def get_stats(self) -> dict[str, int]:
        """仪表盘统计数据."""
        total_accounts = await self.session.scalar(select(func.count()).select_from(AWSAccount))
        active_accounts = await self.session.scalar(
            select(func.count()).select_from(AWSAccount).where(AWSAccount.status == "active")
        )
        total_users = await self.session.scalar(select(func.count()).select_from(ICUser))
        total_subs = await self.session.scalar(select(func.count()).select_from(KiroSubscription))
        active_subs = await self.session.scalar(
            select(func.count())
            .select_from(KiroSubscription)
            .where(KiroSubscription.status == "active")
        )
        pending_subs = await self.session.scalar(
            select(func.count())
            .select_from(ICUser)
            .where(ICUser.pending_subscription_type.is_not(None))
        )
        return {
            "total_accounts": total_accounts or 0,
            "active_accounts": active_accounts or 0,
            "total_users": total_users or 0,
            "total_subscriptions": total_subs or 0,
            "active_subscriptions": active_subs or 0,
            "pending_subscriptions": pending_subs or 0,
        }
