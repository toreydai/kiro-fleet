"""订阅相关 Schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# 订阅类型：旧 → 新，自动重试映射
SUBSCRIPTION_TYPE_ALIASES: dict[str, str] = {
    "Q_DEVELOPER_STANDALONE_PRO": "KIRO_ENTERPRISE_PRO",
    "Q_DEVELOPER_STANDALONE_PRO_PLUS": "KIRO_ENTERPRISE_PRO_PLUS",
    "Q_DEVELOPER_STANDALONE_POWER": "KIRO_ENTERPRISE_PRO_POWER",
}

VALID_SUBSCRIPTION_TYPES = [
    "KIRO_ENTERPRISE_PRO",
    "KIRO_ENTERPRISE_PRO_PLUS",
    "KIRO_ENTERPRISE_PRO_MAX",
    "KIRO_ENTERPRISE_PRO_POWER",
    "Q_DEVELOPER_STANDALONE_PRO",
    "Q_DEVELOPER_STANDALONE_PRO_PLUS",
    "Q_DEVELOPER_STANDALONE_POWER",
]


class SubscriptionAssign(BaseModel):
    ic_user_id: int = Field(..., description="本地 ic_users.id")
    subscription_type: str = Field(..., description="订阅类型")


class SubscriptionChangePlan(BaseModel):
    subscription_type: str = Field(..., description="新的订阅类型")


class SubscriptionResponse(BaseModel):
    id: int
    aws_account_id: int
    user_id: int | None = None
    principal_id: str
    subscription_type: str
    status: str
    start_date: datetime | None = None
    last_synced: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionWithUser(SubscriptionResponse):
    user_name: str | None = None
    user_email: str | None = None
    account_name: str | None = None


class BulkChangePlanRequest(BaseModel):
    subscription_ids: list[int] = Field(..., min_length=1)
    subscription_type: str
