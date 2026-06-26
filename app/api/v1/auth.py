"""认证路由 — 仅做 HTTP 参数校验与响应组装."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.core.rate_limit import limit_login
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MFADisableRequest,
    MFAEnableRequest,
    MFAVerifyRequest,
    RefreshTokenRequest,
    SystemUserCreate,
    SystemUserResetPassword,
    SystemUserResponse,
    SystemUserUpdate,
    TokenResponse,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
async def login(body: LoginRequest, session: SessionDep, _: None = Depends(limit_login)):
    """第一步登录。若启用 MFA 则返回 pre_auth_token."""
    from app.core.exceptions import MFAChallengeRequired

    svc = AuthService(session)
    try:
        tokens = await svc.login(body.username, body.password)
        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        )
    except MFAChallengeRequired as e:
        return JSONResponse(
            status_code=202,
            content={
                "mfa_required": True,
                "pre_auth_token": e.pre_auth_token,
            },
        )


@router.post("/login/mfa", response_model=TokenResponse)
async def verify_mfa(body: MFAVerifyRequest, session: SessionDep):
    """MFA 第二步验证."""
    svc = AuthService(session)
    tokens = await svc.verify_mfa(body.pre_auth_token, body.totp_code)
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshTokenRequest, session: SessionDep):
    svc = AuthService(session)
    tokens = await svc.refresh(body.refresh_token)
    return TokenResponse(**tokens)


@router.post("/logout", response_model=MessageResponse)
async def logout(body: RefreshTokenRequest, session: SessionDep):
    svc = AuthService(session)
    await svc.logout(body.refresh_token)
    return MessageResponse(message="已退出登录")


@router.get("/me", response_model=SystemUserResponse)
async def get_me(current_user: CurrentUser):
    return current_user


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest, current_user: CurrentUser, session: SessionDep
):
    svc = AuthService(session)
    await svc.change_password(current_user.id, body.old_password, body.new_password)
    return MessageResponse(message="密码已修改")


# ── MFA 管理 ──────────────────────────────────────────────────────────────


@router.post("/mfa/setup")
async def setup_mfa(current_user: CurrentUser, session: SessionDep):
    svc = AuthService(session)
    result = await svc.setup_mfa(current_user.id)
    return result


@router.post("/mfa/enable", response_model=MessageResponse)
async def enable_mfa(body: MFAEnableRequest, current_user: CurrentUser, session: SessionDep):
    svc = AuthService(session)
    await svc.enable_mfa(current_user.id, body.totp_code)
    return MessageResponse(message="MFA 已启用")


@router.post("/mfa/disable", response_model=MessageResponse)
async def disable_mfa(body: MFADisableRequest, current_user: CurrentUser, session: SessionDep):
    svc = AuthService(session)
    await svc.disable_mfa(current_user.id, body.totp_code)
    return MessageResponse(message="MFA 已禁用")


# ── 系统用户管理（仅管理员）───────────────────────────────────────────────


@router.get("/users", response_model=list[SystemUserResponse])
async def list_system_users(admin: AdminUser, session: SessionDep):
    svc = AuthService(session)
    return await svc.list_system_users()


@router.post("/users", response_model=SystemUserResponse)
async def create_system_user(body: SystemUserCreate, admin: AdminUser, session: SessionDep):
    svc = AuthService(session)
    return await svc.create_system_user(
        username=body.username,
        email=body.email,
        password=body.password,
        is_admin=body.is_admin,
        operator=admin.username,
    )


@router.get("/users/{user_id}", response_model=SystemUserResponse)
async def get_system_user(user_id: int, admin: AdminUser, session: SessionDep):
    svc = AuthService(session)
    return await svc.get_system_user(user_id)


@router.patch("/users/{user_id}", response_model=SystemUserResponse)
async def update_system_user(
    user_id: int, body: SystemUserUpdate, admin: AdminUser, session: SessionDep
):
    svc = AuthService(session)
    updates = body.model_dump(exclude_none=True)
    return await svc.update_system_user(user_id, **updates)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_system_user(user_id: int, admin: AdminUser, session: SessionDep):
    svc = AuthService(session)
    await svc.delete_system_user(user_id)
    return MessageResponse(message="用户已删除")


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
async def reset_system_user_password(
    user_id: int, body: SystemUserResetPassword, admin: AdminUser, session: SessionDep
):
    svc = AuthService(session)
    await svc.admin_reset_password(user_id, body.new_password)
    return MessageResponse(message="密码已重置")
