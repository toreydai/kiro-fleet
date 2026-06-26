"""依赖注入：get_current_user / get_session / require_admin."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.db import AsyncSession, get_session
from app.core.exceptions import InvalidTokenError
from app.models.system_user import SystemUser

bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> SystemUser:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MISSING_TOKEN", "message": "缺少 Bearer token"}},
        )
    from app.services.auth_service import AuthService

    auth_svc = AuthService(session)
    try:
        user = await auth_svc.get_current_user(credentials.credentials)
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": e.code, "message": e.message}},
        )
    return user


CurrentUser = Annotated[SystemUser, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> SystemUser:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "PERMISSION_DENIED", "message": "需要管理员权限"}},
        )
    return current_user


AdminUser = Annotated[SystemUser, Depends(require_admin)]
