"""账号路由."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.schemas.account import AccountCreate, AccountResponse, AccountStats, AccountUpdate
from app.schemas.common import MessageResponse
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["账号管理"])


@router.get("", response_model=list[AccountResponse])
async def list_accounts(current_user: CurrentUser, session: SessionDep):
    svc = AccountService(session)
    return await svc.list_accounts()


@router.post("", response_model=AccountResponse)
async def create_account(body: AccountCreate, admin: AdminUser, session: SessionDep):
    svc = AccountService(session)
    return await svc.create_account(body)


@router.get("/stats", response_model=AccountStats)
async def get_stats(current_user: CurrentUser, session: SessionDep):
    svc = AccountService(session)
    data = await svc.get_stats()
    return AccountStats(**data)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int, current_user: CurrentUser, session: SessionDep):
    svc = AccountService(session)
    return await svc.get_account(account_id)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int, body: AccountUpdate, admin: AdminUser, session: SessionDep
):
    svc = AccountService(session)
    return await svc.update_account(account_id, body)


@router.delete("/{account_id}", response_model=MessageResponse)
async def delete_account(account_id: int, admin: AdminUser, session: SessionDep):
    svc = AccountService(session)
    await svc.delete_account(account_id)
    return MessageResponse(message="账号已删除")


@router.post("/{account_id}/verify", response_model=AccountResponse)
async def verify_account(account_id: int, admin: AdminUser, session: SessionDep):
    svc = AccountService(session)
    return await svc.verify_account(account_id)


@router.post("/{account_id}/sync", response_model=MessageResponse)
async def sync_account(account_id: int, current_user: CurrentUser, session: SessionDep):
    from app.services.sync_service import SyncService

    svc = SyncService(session)
    result = await svc.sync_account(account_id)
    return MessageResponse(message=f"同步完成: {result}")
