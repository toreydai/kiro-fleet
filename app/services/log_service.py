"""操作日志业务逻辑."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.subscription_repo import OperationLogRepository

logger = logging.getLogger(__name__)


class LogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = OperationLogRepository(session)

    async def log(
        self,
        operation: str,
        status: str,
        account_id: int | None = None,
        target: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        operator: str | None = None,
    ) -> object:
        """记录操作日志."""
        return await self.repo.create(
            aws_account_id=account_id,
            operation=operation,
            target=target,
            status=status,
            message=message,
            details=details,
            operator=operator,
        )

    async def list_logs(
        self,
        account_id: int | None = None,
        operation: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list, int]:
        return await self.repo.list_by_account(
            account_id=account_id,
            operation=operation,
            status=status,
            page=page,
            page_size=page_size,
        )

    async def get_log(self, log_id: int) -> object:
        from app.core.exceptions import NotFoundError

        log = await self.repo.get_by_id(log_id)
        if not log:
            raise NotFoundError("操作日志", log_id)
        return log
