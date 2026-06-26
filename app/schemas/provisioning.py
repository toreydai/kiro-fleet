"""批量开通相关 Schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProvisionPlan(BaseModel):
    """单个套餐的开通计划."""

    subscription_type: str = Field(..., description="订阅类型，如 KIRO_ENTERPRISE_PRO")
    count: int = Field(..., ge=1, le=1000, description="该套餐需开通的用户数量")


class QuickProvisionRequest(BaseModel):
    """一键按套餐数量批量开通."""

    plans: list[ProvisionPlan] = Field(..., min_length=1, description="套餐-数量列表")
    domain: str = Field(..., description="邮箱域名，如 d-xxxxxxxx.awsapps.com")
    prefix: str = Field(..., min_length=1, max_length=32, description="用户名前缀")
    group_id: str | None = Field(None, description="可选：将新用户加入指定 IDC Group 的 GroupId")


class BatchUserImportItem(BaseModel):
    """列表导入单个用户."""

    user_name: str = Field(..., min_length=1, max_length=128)
    email: str
    given_name: str | None = None
    family_name: str | None = None
    subscription_type: str | None = None


class BatchImportRequest(BaseModel):
    """粘贴列表批量导入."""

    users: list[BatchUserImportItem] = Field(..., min_length=1)
    default_subscription_type: str | None = None


class TaskProgressEvent(BaseModel):
    """SSE 进度事件."""

    task_id: int
    status: str
    progress: int
    total_count: int
    success_count: int
    failed_count: int
    current_user: str | None = None
    message: str | None = None


class BatchTaskResponse(BaseModel):
    id: int
    aws_account_id: int
    task_type: str
    status: str
    progress: int
    total_count: int
    success_count: int
    failed_count: int
    result: dict | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ExportResponse(BaseModel):
    task_id: int
    export_path: str
    file_name: str
    record_count: int
