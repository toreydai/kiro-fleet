"""账号相关 Schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    access_key_id: str = Field(..., min_length=16, max_length=128)
    secret_access_key: str = Field(..., min_length=1)
    sso_region: str = Field(..., min_length=1, max_length=32)
    kiro_region: str = Field(..., min_length=1, max_length=32)
    instance_arn: str = Field(..., min_length=1)
    identity_store_id: str = Field(..., min_length=1, max_length=64)
    kiro_login_url: str | None = None
    sync_interval_minutes: int = Field(default=10, ge=1, le=1440)
    is_default: bool = False


class AccountUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    sso_region: str | None = None
    kiro_region: str | None = None
    instance_arn: str | None = None
    identity_store_id: str | None = None
    kiro_login_url: str | None = None
    sync_interval_minutes: int | None = Field(None, ge=1, le=1440)
    is_default: bool | None = None


class AccountResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    sso_region: str
    kiro_region: str
    instance_arn: str
    identity_store_id: str
    status: str
    last_verified: datetime | None = None
    sync_interval_minutes: int
    last_synced: datetime | None = None
    is_default: bool
    kiro_login_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountStats(BaseModel):
    total_accounts: int
    active_accounts: int
    total_users: int
    total_subscriptions: int
    active_subscriptions: int
    pending_subscriptions: int
