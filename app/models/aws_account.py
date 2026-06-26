"""AWS 账号相关 ORM 模型."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class AWSAccount(Base):
    __tablename__ = "aws_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    # AK/SK 均以 AES-256-GCM 加密后存储
    access_key_id: Mapped[str] = mapped_column(Text, nullable=False)
    secret_access_key: Mapped[str] = mapped_column(Text, nullable=False)
    sso_region: Mapped[str] = mapped_column(String(32), nullable=False)
    kiro_region: Mapped[str] = mapped_column(String(32), nullable=False)
    instance_arn: Mapped[str] = mapped_column(String(256), nullable=False)
    identity_store_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    permissions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kiro_login_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ic_users: Mapped[list[ICUser]] = relationship(
        "ICUser", back_populates="account", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list[KiroSubscription]] = relationship(
        "KiroSubscription", back_populates="account", cascade="all, delete-orphan"
    )
    operation_logs: Mapped[list[OperationLog]] = relationship(
        "OperationLog", back_populates="account", cascade="all, delete-orphan"
    )
    batch_tasks: Mapped[list[BatchTask]] = relationship(
        "BatchTask", back_populates="account", cascade="all, delete-orphan"
    )


class ICUser(Base):
    __tablename__ = "ic_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aws_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)  # AWS UserId
    user_name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    given_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    family_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    groups: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pending_subscription_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    account: Mapped[AWSAccount] = relationship("AWSAccount", back_populates="ic_users")
    subscriptions: Mapped[list[KiroSubscription]] = relationship(
        "KiroSubscription", back_populates="ic_user", cascade="all, delete-orphan"
    )
    credit_usages: Mapped[list[CreditUsage]] = relationship(
        "CreditUsage", back_populates="ic_user", cascade="all, delete-orphan"
    )


class KiroSubscription(Base):
    __tablename__ = "kiro_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aws_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ic_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    principal_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    subscription_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    account: Mapped[AWSAccount] = relationship("AWSAccount", back_populates="subscriptions")
    ic_user: Mapped[ICUser | None] = relationship("ICUser", back_populates="subscriptions")


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aws_account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("aws_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    operation: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    operator: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    account: Mapped[AWSAccount | None] = relationship("AWSAccount", back_populates="operation_logs")


class CreditUsage(Base):
    __tablename__ = "credit_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ic_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    total_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    feature_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ic_user: Mapped[ICUser | None] = relationship("ICUser", back_populates="credit_usages")


class BatchTask(Base):
    __tablename__ = "batch_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aws_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    targets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[AWSAccount] = relationship("AWSAccount", back_populates="batch_tasks")
