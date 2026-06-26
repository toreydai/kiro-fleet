"""initial_schema

Revision ID: adc9fdb4ad18
Revises: 
Create Date: 2026-06-24 02:20:48.406190
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'adc9fdb4ad18'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "aws_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("access_key_id", sa.Text(), nullable=False),
        sa.Column("secret_access_key", sa.Text(), nullable=False),
        sa.Column("sso_region", sa.String(32), nullable=False),
        sa.Column("kiro_region", sa.String(32), nullable=False),
        sa.Column("instance_arn", sa.String(256), nullable=False),
        sa.Column("identity_store_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("last_verified", sa.DateTime(timezone=True)),
        sa.Column("permissions", sa.JSON()),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("last_synced", sa.DateTime(timezone=True)),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("kiro_login_url", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "system_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("totp_secret", sa.String(64)),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_system_users_username", "system_users", ["username"], unique=True)
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("system_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_table(
        "ic_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aws_account_id", sa.Integer(), sa.ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("user_name", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(256)), sa.Column("email", sa.String(255)),
        sa.Column("given_name", sa.String(128)), sa.Column("family_name", sa.String(128)),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("groups", sa.JSON()),
        sa.Column("pending_subscription_type", sa.String(64)),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("last_synced", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, cols in (("ix_ic_users_aws_account_id", ["aws_account_id"]), ("ix_ic_users_user_id", ["user_id"]), ("ix_ic_users_email", ["email"])):
        op.create_index(name, "ic_users", cols)
    op.create_table(
        "kiro_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aws_account_id", sa.Integer(), sa.ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("ic_users.id", ondelete="SET NULL")),
        sa.Column("principal_id", sa.String(128), nullable=False),
        sa.Column("subscription_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True)),
        sa.Column("last_synced", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, cols in (("ix_kiro_subscriptions_aws_account_id", ["aws_account_id"]), ("ix_kiro_subscriptions_user_id", ["user_id"]), ("ix_kiro_subscriptions_principal_id", ["principal_id"])):
        op.create_index(name, "kiro_subscriptions", cols)
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aws_account_id", sa.Integer(), sa.ForeignKey("aws_accounts.id", ondelete="SET NULL")),
        sa.Column("operation", sa.String(64), nullable=False), sa.Column("target", sa.String(256)),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("message", sa.Text()),
        sa.Column("details", sa.JSON()), sa.Column("operator", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for name, cols in (("ix_operation_logs_aws_account_id", ["aws_account_id"]), ("ix_operation_logs_operation", ["operation"]), ("ix_operation_logs_created_at", ["created_at"])):
        op.create_index(name, "operation_logs", cols)
    op.create_table(
        "credit_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("ic_users.id", ondelete="SET NULL")),
        sa.Column("date", sa.String(10), nullable=False), sa.Column("total_credits", sa.Integer(), nullable=False),
        sa.Column("feature_breakdown", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_credit_usage_user_id", "credit_usage", ["user_id"])
    op.create_index("ix_credit_usage_date", "credit_usage", ["date"])
    op.create_table(
        "batch_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aws_account_id", sa.Integer(), sa.ForeignKey("aws_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_type", sa.String(32), nullable=False), sa.Column("targets", sa.JSON()),
        sa.Column("params", sa.JSON()), sa.Column("status", sa.String(16), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False), sa.Column("total_count", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False), sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON()), sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_batch_tasks_aws_account_id", "batch_tasks", ["aws_account_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("batch_tasks")
    op.drop_table("credit_usage")
    op.drop_table("operation_logs")
    op.drop_table("kiro_subscriptions")
    op.drop_table("ic_users")
    op.drop_table("refresh_tokens")
    op.drop_table("system_users")
    op.drop_table("aws_accounts")
