"""批量开通的确定性业务规则测试（不调用 AWS）。"""

from __future__ import annotations

import pytest

from app.services.provisioning_service import ProvisioningService


@pytest.mark.asyncio
async def test_generated_usernames_are_unique_and_skip_existing(monkeypatch, session):
    """同一秒内生成的用户名也必须避开已有名称。"""
    service = ProvisioningService(session)
    monkeypatch.setattr("app.services.provisioning_service.time.time", lambda: 1_700_000_000)
    existing = {"kiro1700000000000"}

    names = service._generate_usernames("kiro", 3, existing)

    assert names == [
        "kiro1700000000001",
        "kiro1700000000002",
        "kiro1700000000003",
    ]
    assert len(set(names)) == 3
