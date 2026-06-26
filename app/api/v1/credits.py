"""Credit 用量路由."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.services.credit_service import CreditService

router = APIRouter(tags=["Credit 用量"])


@router.get("/accounts/{account_id}/credits", response_model=dict)
async def list_credits(
    account_id: int,
    current_user: CurrentUser,
    session: SessionDep,
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """查询账号下的 Credit 用量记录."""
    svc = CreditService(session)
    items, total = await svc.list_credits(account_id, start_date, end_date, page, page_size)
    return {
        "items": [
            {
                "id": c.id,
                "user_id": c.user_id,
                "date": c.date,
                "total_credits": c.total_credits,
                "feature_breakdown": c.feature_breakdown,
                "created_at": c.created_at.isoformat(),
            }
            for c in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/accounts/{account_id}/credits/sync", response_model=dict)
async def sync_credits(account_id: int, admin: AdminUser, session: SessionDep):
    """触发同步 Credit 用量数据."""
    svc = CreditService(session)
    result = await svc.sync_credits(account_id)
    return result


@router.get("/users/{user_id}/credits", response_model=list)
async def list_user_credits(
    user_id: int,
    current_user: CurrentUser,
    session: SessionDep,
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    svc = CreditService(session)
    items = await svc.list_user_credits(user_id, start_date, end_date)
    return [
        {
            "id": c.id,
            "date": c.date,
            "total_credits": c.total_credits,
            "feature_breakdown": c.feature_breakdown,
        }
        for c in items
    ]
