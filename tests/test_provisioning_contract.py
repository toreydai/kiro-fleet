"""批量开通 API 契约测试 — 确保前后端字段名一致，防止回归。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.provisioning import BatchImportRequest, BatchUserImportItem, QuickProvisionRequest


# ── QuickProvisionRequest 契约 ─────────────────────────────────────────────


def test_quick_provision_accepts_correct_payload():
    """前端实际发送的字段名必须被后端接受."""
    data = QuickProvisionRequest.model_validate(
        {
            "prefix": "kiro",
            "domain": "example.com",
            "plans": [
                {"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 2},
                {"subscription_type": "KIRO_ENTERPRISE_PRO_POWER", "count": 1},
            ],
        }
    )
    assert data.prefix == "kiro"
    assert data.domain == "example.com"
    assert len(data.plans) == 2
    assert data.plans[0].subscription_type == "KIRO_ENTERPRISE_PRO"
    assert data.plans[0].count == 2


def test_quick_provision_rejects_legacy_plan_field():
    """旧字段名 'plan' 应被拒绝（触发本次 422 的根因）."""
    with pytest.raises(ValidationError) as exc:
        QuickProvisionRequest.model_validate(
            {
                "prefix": "kiro",
                "domain": "example.com",
                "plans": [{"plan": "KIRO_ENTERPRISE_PRO", "count": 2}],
            }
        )
    missing = {
        ".".join(str(p) for p in e["loc"])
        for e in exc.value.errors()
        if e["type"] == "missing"
    }
    assert any("subscription_type" in f for f in missing)


def test_quick_provision_requires_domain():
    """domain 为必填，缺少时应报 422."""
    with pytest.raises(ValidationError) as exc:
        QuickProvisionRequest.model_validate(
            {
                "prefix": "kiro",
                "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 1}],
            }
        )
    missing = {
        ".".join(str(p) for p in e["loc"])
        for e in exc.value.errors()
        if e["type"] == "missing"
    }
    assert "domain" in missing


def test_quick_provision_requires_at_least_one_plan():
    """plans 列表不能为空."""
    with pytest.raises(ValidationError):
        QuickProvisionRequest.model_validate(
            {"prefix": "kiro", "domain": "example.com", "plans": []}
        )


def test_quick_provision_plan_count_must_be_positive():
    """count 必须 >= 1."""
    with pytest.raises(ValidationError):
        QuickProvisionRequest.model_validate(
            {
                "prefix": "kiro",
                "domain": "example.com",
                "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 0}],
            }
        )


# ── BatchImportRequest 契约 ────────────────────────────────────────────────


def test_batch_import_accepts_correct_payload():
    data = BatchImportRequest.model_validate(
        {
            "users": [
                {
                    "user_name": "alice",
                    "email": "alice@example.com",
                    "given_name": "Alice",
                    "family_name": "Smith",
                    "subscription_type": "KIRO_ENTERPRISE_PRO",
                }
            ],
            "default_subscription_type": None,
        }
    )
    assert data.users[0].user_name == "alice"
    assert data.users[0].email == "alice@example.com"


def test_batch_import_requires_at_least_one_user():
    with pytest.raises(ValidationError):
        BatchImportRequest.model_validate({"users": []})


def test_batch_import_user_requires_user_name():
    with pytest.raises(ValidationError):
        BatchImportRequest.model_validate(
            {"users": [{"email": "bob@example.com"}]}
        )
