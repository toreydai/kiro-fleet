"""订阅路由."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.schemas.common import MessageResponse
from app.schemas.subscription import (
    BulkChangePlanRequest,
    SubscriptionAssign,
    SubscriptionChangePlan,
    SubscriptionResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(tags=["订阅管理"])


# ── 账号级订阅 ────────────────────────────────────────────────────────────


@router.get("/accounts/{account_id}/subscriptions", response_model=dict)
async def list_subscriptions(
    account_id: int,
    current_user: CurrentUser,
    session: SessionDep,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    svc = SubscriptionService(session)
    items, total = await svc.list_by_account(account_id, status, page, page_size)
    return {
        "items": [SubscriptionResponse.model_validate(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/accounts/{account_id}/subscriptions", response_model=SubscriptionResponse)
async def assign_subscription(
    account_id: int, body: SubscriptionAssign, admin: AdminUser, session: SessionDep
):
    svc = SubscriptionService(session)
    return await svc.assign(
        account_id=account_id,
        ic_user_id=body.ic_user_id,
        subscription_type=body.subscription_type,
        operator=admin.username,
    )


@router.patch("/accounts/{account_id}/subscriptions/{sub_id}", response_model=SubscriptionResponse)
async def change_plan(
    account_id: int,
    sub_id: int,
    body: SubscriptionChangePlan,
    admin: AdminUser,
    session: SessionDep,
):
    svc = SubscriptionService(session)
    return await svc.change_plan(account_id, sub_id, body.subscription_type, admin.username)


@router.delete("/accounts/{account_id}/subscriptions/{sub_id}", response_model=MessageResponse)
async def cancel_subscription(account_id: int, sub_id: int, admin: AdminUser, session: SessionDep):
    svc = SubscriptionService(session)
    await svc.cancel(account_id, sub_id, admin.username)
    return MessageResponse(message="订阅已取消")


@router.post("/accounts/{account_id}/subscriptions/bulk-change-plan", response_model=dict)
async def bulk_change_plan(
    account_id: int,
    body: BulkChangePlanRequest,
    admin: AdminUser,
    session: SessionDep,
):
    svc = SubscriptionService(session)
    return await svc.bulk_change_plan(
        account_id, body.subscription_ids, body.subscription_type, admin.username
    )


# ── 跨账号订阅总览 ────────────────────────────────────────────────────────


@router.get("/subscriptions", response_model=dict)
async def list_all_subscriptions(
    current_user: CurrentUser,
    session: SessionDep,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """跨账号订阅总览（honcho 中存在但未注册，正式启用）."""
    svc = SubscriptionService(session)
    items, total = await svc.list_all(status, page, page_size)
    return {
        "items": [SubscriptionResponse.model_validate(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/canceled-subscriptions", response_model=dict)
async def list_canceled_subscriptions(
    current_user: CurrentUser,
    session: SessionDep,
    account_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    svc = SubscriptionService(session)
    items, total = await svc.list_canceled(account_id, page, page_size)
    return {
        "items": [SubscriptionResponse.model_validate(s) for s in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
