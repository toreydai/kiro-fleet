"""订阅 & 日志 & 批量任务数据访问层."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aws_account import BatchTask, CreditUsage, KiroSubscription, OperationLog


class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, sub_id: int) -> KiroSubscription | None:
        return await self.session.get(KiroSubscription, sub_id)

    async def get_by_principal(self, account_id: int, principal_id: str) -> KiroSubscription | None:
        stmt = select(KiroSubscription).where(
            and_(
                KiroSubscription.aws_account_id == account_id,
                KiroSubscription.principal_id == principal_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_account(
        self,
        account_id: int,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KiroSubscription], int]:
        stmt = select(KiroSubscription).where(KiroSubscription.aws_account_id == account_id)
        if status:
            stmt = stmt.where(KiroSubscription.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt) or 0

        stmt = stmt.order_by(KiroSubscription.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_all(
        self,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KiroSubscription], int]:
        """跨账号订阅总览."""
        stmt = select(KiroSubscription)
        if status:
            stmt = stmt.where(KiroSubscription.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt) or 0

        stmt = stmt.order_by(KiroSubscription.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_canceled(
        self, account_id: int | None = None, page: int = 1, page_size: int = 50
    ) -> tuple[list[KiroSubscription], int]:
        stmt = select(KiroSubscription).where(KiroSubscription.status == "canceled")
        if account_id:
            stmt = stmt.where(KiroSubscription.aws_account_id == account_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt) or 0
        stmt = stmt.order_by(KiroSubscription.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, **kwargs: Any) -> KiroSubscription:
        sub = KiroSubscription(**kwargs)
        self.session.add(sub)
        await self.session.flush()
        await self.session.refresh(sub)
        return sub

    async def update(self, sub: KiroSubscription, **kwargs: Any) -> KiroSubscription:
        for key, value in kwargs.items():
            setattr(sub, key, value)
        await self.session.flush()
        await self.session.refresh(sub)
        return sub

    async def delete(self, sub: KiroSubscription) -> None:
        await self.session.delete(sub)
        await self.session.flush()


class OperationLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs: Any) -> OperationLog:
        log = OperationLog(**kwargs)
        self.session.add(log)
        await self.session.flush()
        return log

    async def list_by_account(
        self,
        account_id: int | None = None,
        operation: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[OperationLog], int]:
        stmt = select(OperationLog)
        if account_id:
            stmt = stmt.where(OperationLog.aws_account_id == account_id)
        if operation:
            stmt = stmt.where(OperationLog.operation == operation)
        if status:
            stmt = stmt.where(OperationLog.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt) or 0

        stmt = stmt.order_by(OperationLog.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_id(self, log_id: int) -> OperationLog | None:
        return await self.session.get(OperationLog, log_id)


class BatchTaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, task_id: int) -> BatchTask | None:
        return await self.session.get(BatchTask, task_id)

    async def create(self, **kwargs: Any) -> BatchTask:
        task = BatchTask(**kwargs)
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def update(self, task: BatchTask, **kwargs: Any) -> BatchTask:
        for key, value in kwargs.items():
            setattr(task, key, value)
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def list_by_account(
        self, account_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[BatchTask], int]:
        stmt = select(BatchTask).where(BatchTask.aws_account_id == account_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt) or 0
        stmt = stmt.order_by(BatchTask.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total


class CreditUsageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self, user_id: int, date: str, total_credits: int, breakdown: dict | None = None
    ) -> CreditUsage:
        stmt = select(CreditUsage).where(
            and_(CreditUsage.user_id == user_id, CreditUsage.date == date)
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.total_credits = total_credits
            if breakdown is not None:
                existing.feature_breakdown = breakdown
            await self.session.flush()
            return existing
        else:
            cu = CreditUsage(
                user_id=user_id,
                date=date,
                total_credits=total_credits,
                feature_breakdown=breakdown,
            )
            self.session.add(cu)
            await self.session.flush()
            await self.session.refresh(cu)
            return cu

    async def list_by_user(
        self, user_id: int, start_date: str | None = None, end_date: str | None = None
    ) -> list[CreditUsage]:
        stmt = select(CreditUsage).where(CreditUsage.user_id == user_id)
        if start_date:
            stmt = stmt.where(CreditUsage.date >= start_date)
        if end_date:
            stmt = stmt.where(CreditUsage.date <= end_date)
        stmt = stmt.order_by(CreditUsage.date.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_account(
        self,
        account_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[CreditUsage], int]:
        from app.models.aws_account import ICUser

        stmt = (
            select(CreditUsage)
            .join(ICUser, CreditUsage.user_id == ICUser.id)
            .where(ICUser.aws_account_id == account_id)
        )
        if start_date:
            stmt = stmt.where(CreditUsage.date >= start_date)
        if end_date:
            stmt = stmt.where(CreditUsage.date <= end_date)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await self.session.scalar(count_stmt) or 0

        stmt = stmt.order_by(CreditUsage.date.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
