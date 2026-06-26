"""AWS account payload contract tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.account import AccountCreate


def _account_payload() -> dict[str, object]:
    return {
        "name": "contract-test-account",
        "description": "created by account payload contract test",
        "access_key_id": "AKIATESTACCOUNT123",
        "secret_access_key": "test-secret-access-key",
        "sso_region": "us-east-1",
        "kiro_region": "us-east-1",
        "instance_arn": "arn:aws:sso:::instance/ssoins-1234567890abcdef",
        "identity_store_id": "d-1234567890",
        "kiro_login_url": "https://d-1234567890.awsapps.com/start",
        "sync_interval_minutes": 10,
        "is_default": True,
    }


def test_account_create_accepts_frontend_payload():
    data = AccountCreate.model_validate(_account_payload())

    assert data.name == "contract-test-account"
    assert data.access_key_id == "AKIATESTACCOUNT123"
    assert data.secret_access_key == "test-secret-access-key"
    assert data.sso_region == "us-east-1"
    assert data.kiro_region == "us-east-1"
    assert data.instance_arn == "arn:aws:sso:::instance/ssoins-1234567890abcdef"
    assert data.identity_store_id == "d-1234567890"
    assert data.sync_interval_minutes == 10
    assert data.is_default is True


def test_account_create_rejects_legacy_frontend_payload():
    with pytest.raises(ValidationError) as exc_info:
        AccountCreate.model_validate(
            {
                "name": "legacy-form-account",
                "account_id": "123456789012",
                "region": "us-east-1",
                "instance_arn": "arn:aws:sso:::instance/ssoins-1234567890abcdef",
                "identity_store_id": "d-1234567890",
            }
        )

    missing_fields = {
        ".".join(str(part) for part in error["loc"])
        for error in exc_info.value.errors()
        if error["type"] == "missing"
    }
    assert "access_key_id" in missing_fields
    assert "secret_access_key" in missing_fields
    assert "sso_region" in missing_fields
    assert "kiro_region" in missing_fields
