"""IC 用户路由 — 字面路径必须在 /{id} 之前以防路由遮蔽."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.schemas.common import MessageResponse
from app.schemas.user import (
    GroupAddRequest,
    ICUserCreate,
    ICUserListItem,
    ICUserResponse,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/accounts/{account_id}/users", tags=["IC 用户"])


@router.get("", response_model=dict)
async def list_users(
    account_id: int,
    current_user: CurrentUser,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = None,
):
    svc = UserService(session)
    items, total = await svc.list_users(account_id, page, page_size, search)
    return {
        "items": [ICUserListItem.model_validate(u) for u in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.post("", response_model=ICUserResponse)
async def create_user(account_id: int, body: ICUserCreate, admin: AdminUser, session: SessionDep):
    svc = UserService(session)
    return await svc.create_user(
        account_id=account_id,
        user_name=body.user_name,
        email=body.email,
        given_name=body.given_name,
        family_name=body.family_name,
        display_name=body.display_name,
        operator=admin.username,
    )


# 字面路径必须在 /{user_id} 之前注册
@router.get("/groups")
async def list_groups(account_id: int, current_user: CurrentUser, session: SessionDep):
    """列出账号下的所有 Identity Center 用户组."""
    svc = UserService(session)
    return {"groups": await svc.list_groups(account_id)}


@router.get("/{user_id}", response_model=ICUserResponse)
async def get_user(account_id: int, user_id: int, current_user: CurrentUser, session: SessionDep):
    svc = UserService(session)
    return await svc.get_user(account_id, user_id)


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(account_id: int, user_id: int, admin: AdminUser, session: SessionDep):
    svc = UserService(session)
    await svc.delete_user(account_id, user_id, operator=admin.username)
    return MessageResponse(message="用户已删除")


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
async def reset_password(account_id: int, user_id: int, admin: AdminUser, session: SessionDep):
    svc = UserService(session)
    await svc.reset_password(account_id, user_id, operator=admin.username)
    return MessageResponse(message="密码重置邮件已发送")


@router.post("/{user_id}/verify-email", response_model=MessageResponse)
async def send_email_verification(
    account_id: int, user_id: int, admin: AdminUser, session: SessionDep
):
    svc = UserService(session)
    await svc.send_email_verification(account_id, user_id, operator=admin.username)
    return MessageResponse(message="邮箱验证邮件已发送")


@router.post("/{user_id}/add-to-group", response_model=MessageResponse)
async def add_to_group(
    account_id: int,
    user_id: int,
    body: GroupAddRequest,
    admin: AdminUser,
    session: SessionDep,
):
    svc = UserService(session)
    await svc.add_user_to_group(account_id, user_id, body.group_id, operator=admin.username)
    return MessageResponse(message="已添加到用户组")
