"""可复用后台任务函数 — 只传标量参数，内部创建独立 session."""

from __future__ import annotations

import logging
from typing import Any

from app.core.db import get_session_maker

logger = logging.getLogger(__name__)


async def provision_subscription(
    account_id: int,
    ic_user_id: int,
    principal_id: str,
    sub_type: str,
) -> dict[str, Any]:
    """为单个 IC 用户分配订阅（后台重试用）."""
    async with get_session_maker()() as session:
        try:
            from app.services.subscription_service import SubscriptionService

            svc = SubscriptionService(session)
            sub = await svc.assign(
                account_id=account_id,
                ic_user_id=ic_user_id,
                subscription_type=sub_type,
                operator="background",
            )
            await session.commit()
            logger.info(
                "Background provision success: account=%d user=%d type=%s",
                account_id,
                ic_user_id,
                sub_type,
            )
            return {"success": True, "subscription_id": sub.id}
        except Exception as e:
            await session.rollback()
            logger.error(
                "Background provision failed: account=%d user=%d type=%s err=%s",
                account_id,
                ic_user_id,
                sub_type,
                e,
            )
            return {"success": False, "error": str(e)}


async def sync_account_task(account_id: int) -> dict[str, Any]:
    """同步单个账号（后台定时任务用）."""
    async with get_session_maker()() as session:
        try:
            from app.services.sync_service import SyncService

            svc = SyncService(session)
            result = await svc.sync_account(account_id)
            await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            logger.error("Sync task failed for account %d: %s", account_id, e)
            return {"error": str(e)}


async def retry_pending_task() -> dict[str, Any]:
    """重试所有 pending subscription（定时任务用）."""
    async with get_session_maker()() as session:
        try:
            from app.services.sync_service import SyncService

            svc = SyncService(session)
            result = await svc.retry_pending_subscriptions()
            await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            logger.error("Retry pending task failed: %s", e)
            return {"error": str(e)}


async def sync_all_task() -> list[dict[str, Any]]:
    """同步所有 active 账号（定时任务用）."""
    async with get_session_maker()() as session:
        try:
            from app.services.sync_service import SyncService

            svc = SyncService(session)
            result = await svc.sync_all_accounts()
            await session.commit()
            return result
        except Exception as e:
            await session.rollback()
            logger.error("Sync all task failed: %s", e)
            return [{"error": str(e)}]
