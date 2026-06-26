"""认证相关 Schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class MFAVerifyRequest(BaseModel):
    pre_auth_token: str = Field(..., description="第一步登录返回的临时令牌")
    totp_code: str = Field(..., min_length=6, max_length=6, description="六位 TOTP 验证码")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MFAChallengeResponse(BaseModel):
    pre_auth_token: str
    mfa_required: bool = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class MFASetupResponse(BaseModel):
    secret: str
    uri: str
    qr_placeholder: str = "请用 TOTP APP 扫描 URI 或手动输入 secret"


class MFAEnableRequest(BaseModel):
    totp_code: str = Field(..., min_length=6, max_length=6)


class MFADisableRequest(BaseModel):
    totp_code: str = Field(..., min_length=6, max_length=6, description="禁用前需验证当前 TOTP")


class SystemUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8)
    is_admin: bool = False


class SystemUserUpdate(BaseModel):
    email: EmailStr | None = None
    is_admin: bool | None = None
    is_active: bool | None = None


class SystemUserResetPassword(BaseModel):
    new_password: str = Field(..., min_length=8)


class SystemUserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    is_active: bool
    mfa_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
