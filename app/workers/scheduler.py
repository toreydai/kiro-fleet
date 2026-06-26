"""APScheduler 定时任务调度器."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.workers.tasks import retry_pending_task, sync_all_task

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


async def _run_sync_all() -> None:
    logger.info("Scheduler: starting sync_all_task")
    results = await sync_all_task()
    logger.info("Scheduler: sync_all_task done, accounts=%d", len(results))


async def _run_retry_pending() -> None:
    logger.info("Scheduler: starting retry_pending_task")
    result = await retry_pending_task()
    logger.info("Scheduler: retry_pending done: %s", result)


def setup_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = get_scheduler()

    # 同步所有账号（每 sync_interval_minutes 分钟）
    scheduler.add_job(
        _run_sync_all,
        trigger=IntervalTrigger(minutes=settings.SYNC_INTERVAL_MINUTES),
        id="sync_all",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 重试 pending 订阅（每 pending_retry_interval_minutes 分钟）
    scheduler.add_job(
        _run_retry_pending,
        trigger=IntervalTrigger(minutes=settings.PENDING_RETRY_INTERVAL_MINUTES),
        id="retry_pending",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    return scheduler


async def start_scheduler() -> None:
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info(
        "Scheduler started: sync_interval=%d min, retry_interval=%d min",
        get_settings().SYNC_INTERVAL_MINUTES,
        get_settings().PENDING_RETRY_INTERVAL_MINUTES,
    )


async def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
