"""操作日志路由."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.services.log_service import LogService

router = APIRouter(prefix="/logs", tags=["操作日志"])


@router.get("", response_model=dict)
async def list_logs(
    current_user: CurrentUser,
    session: SessionDep,
    account_id: int | None = Query(None),
    operation: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    svc = LogService(session)
    items, total = await svc.list_logs(account_id, operation, status, page, page_size)
    return {
        "items": [
            {
                "id": log.id,
                "aws_account_id": log.aws_account_id,
                "operation": log.operation,
                "target": log.target,
                "status": log.status,
                "message": log.message,
                "details": log.details,
                "operator": log.operator,
                "created_at": log.created_at.isoformat(),
            }
            for log in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{log_id}", response_model=dict)
async def get_log(log_id: int, current_user: CurrentUser, session: SessionDep):
    svc = LogService(session)
    log = await svc.get_log(log_id)
    return {
        "id": log.id,
        "aws_account_id": log.aws_account_id,
        "operation": log.operation,
        "target": log.target,
        "status": log.status,
        "message": log.message,
        "details": log.details,
        "operator": log.operator,
        "created_at": log.created_at.isoformat(),
    }
