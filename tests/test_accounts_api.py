"""AWS account payload contract tests + HTTP API tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.account import AccountCreate


# ── Schema 契约 ────────────────────────────────────────────────────────────


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


def test_identity_store_id_format_documented():
    """identity_store_id 必须是 d- 开头（文档要求格式）。"""
    # 正确格式
    data = AccountCreate.model_validate({**_account_payload(), "identity_store_id": "d-906673ece9"})
    assert data.identity_store_id == "d-906673ece9"


# ── HTTP API 测试 ──────────────────────────────────────────────────────────


async def _login_admin(client: AsyncClient, session: AsyncSession) -> str:
    from app.services.auth_service import AuthService

    svc = AuthService(session)
    try:
        await svc.create_system_user(
            username="accadmin",
            email="accadmin@test.com",
            password="AccAdmin@123",
            is_admin=True,
        )
        await session.commit()
    except Exception:
        await session.rollback()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "accadmin", "password": "AccAdmin@123"},
    )
    return resp.json()["access_token"]


async def _login_nonadmin(client: AsyncClient, session: AsyncSession) -> str:
    from app.services.auth_service import AuthService

    svc = AuthService(session)
    try:
        await svc.create_system_user(
            username="accuser",
            email="accuser@test.com",
            password="AccUser@123",
            is_admin=False,
        )
        await session.commit()
    except Exception:
        await session.rollback()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "accuser", "password": "AccUser@123"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
class TestAccountCRUD:
    async def test_create_account_success(self, client: AsyncClient, session: AsyncSession):
        token = await _login_admin(client, session)
        resp = await client.post(
            "/api/v1/accounts",
            json=_account_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "contract-test-account"
        assert data["status"] == "pending"

    async def test_create_account_nonadmin_forbidden(
        self, client: AsyncClient, session: AsyncSession
    ):
        token = await _login_nonadmin(client, session)
        resp = await client.post(
            "/api/v1/accounts",
            json=_account_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_create_duplicate_name_returns_409(
        self, client: AsyncClient, session: AsyncSession
    ):
        token = await _login_admin(client, session)
        payload = _account_payload()

        r1 = await client.post(
            "/api/v1/accounts",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r1.status_code == 200

        r2 = await client.post(
            "/api/v1/accounts",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 409

    async def test_list_accounts_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/accounts")
        assert resp.status_code == 401

    async def test_list_accounts_success(self, client: AsyncClient, session: AsyncSession):
        token = await _login_admin(client, session)
        resp = await client.get(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_get_nonexistent_account_returns_404(
        self, client: AsyncClient, session: AsyncSession
    ):
        token = await _login_admin(client, session)
        resp = await client.get(
            "/api/v1/accounts/999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    async def test_delete_account_success(self, client: AsyncClient, session: AsyncSession):
        token = await _login_admin(client, session)
        create_resp = await client.post(
            "/api/v1/accounts",
            json={**_account_payload(), "name": "delete-me"},
            headers={"Authorization": f"Bearer {token}"},
        )
        account_id = create_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_resp.status_code == 200

        get_resp = await client.get(
            f"/api/v1/accounts/{account_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 404
