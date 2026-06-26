"""IC 用户相关 Schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ICUserCreate(BaseModel):
    user_name: str = Field(..., min_length=1, max_length=128)
    email: EmailStr
    given_name: str | None = None
    family_name: str | None = None
    display_name: str | None = None
    password: str | None = Field(None, min_length=8, description="初始密码，为空则发送邮件重置")


class ICUserUpdate(BaseModel):
    display_name: str | None = None
    given_name: str | None = None
    family_name: str | None = None


class ICUserResponse(BaseModel):
    id: int
    aws_account_id: int
    user_id: str
    user_name: str
    display_name: str | None = None
    email: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    status: str
    groups: list | None = None
    pending_subscription_type: str | None = None
    email_verified: bool
    last_synced: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupAddRequest(BaseModel):
    group_id: str = Field(..., description="Identity Center Group ID")


class UserGroupInfo(BaseModel):
    group_id: str
    group_name: str | None = None


class ICUserListItem(BaseModel):
    id: int
    user_id: str
    user_name: str
    display_name: str | None = None
    email: str | None = None
    status: str
    email_verified: bool
    pending_subscription_type: str | None = None

    model_config = {"from_attributes": True}


class BatchUserCreateItem(BaseModel):
    user_name: str
    email: EmailStr
    given_name: str | None = None
    family_name: str | None = None
    subscription_type: str | None = None
