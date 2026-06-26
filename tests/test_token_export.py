"""账户导出 JSON 测试（AWS Token API 使用替身，不访问真实 AWS）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import TokenExportConfigurationError
from app.services.token_export_service import TokenExportService


@pytest.mark.asyncio
async def test_export_entry_matches_consumer_schema(session):
    service = TokenExportService(session)
    service.get_sso_access_token = AsyncMock(return_value=("idc-access-token", 1_700_000_000_000))
    account = SimpleNamespace(sso_region="us-east-1")
    user = SimpleNamespace(user_name="kiro_001", email="kiro_001@example.com")
    subscription = SimpleNamespace(
        subscription_type="Q_DEVELOPER_STANDALONE_POWER",
        start_date=None,
    )

    entry = await service._build_entry(account, user, subscription, "d-1234abcd")

    assert entry["email"] == "kiro_001@example.com"
    assert entry["userId"] == "d-1234abcd.kiro_001"
    assert entry["credentials"]["accessToken"] == "idc-access-token"
    assert entry["credentials"]["expiresAt"] == 1_700_000_000_000
    assert entry["subscription"]["rawType"] == "Q_DEVELOPER_STANDALONE_POWER"
    assert entry["subscription"]["title"] == "KIRO POWER"
    assert entry["usage"]["limit"] == 10000
    assert entry["lastCheckedAt"] == entry["createdAt"]


@pytest.mark.asyncio
async def test_export_requires_trusted_issuer_configuration(session):
    service = TokenExportService(session)

    with pytest.raises(TokenExportConfigurationError):
        await service.get_sso_access_token(SimpleNamespace(), "user@example.com")
