"""批量开通 HTTP API 测试（AWS 调用全部 mock）。"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

# ── fixtures ──────────────────────────────────────────────────────────────


async def _login_admin(client: AsyncClient, session: AsyncSession) -> str:
    from app.services.auth_service import AuthService

    svc = AuthService(session)
    try:
        await svc.create_system_user(
            username="provadmin",
            email="provadmin@test.com",
            password="ProvAdmin@123",
            is_admin=True,
        )
        await session.commit()
    except Exception:
        await session.rollback()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "provadmin", "password": "ProvAdmin@123"},
    )
    return resp.json()["access_token"]


async def _login_nonadmin(client: AsyncClient, session: AsyncSession) -> str:
    from app.services.auth_service import AuthService

    svc = AuthService(session)
    try:
        await svc.create_system_user(
            username="provuser",
            email="provuser@test.com",
            password="ProvUser@123",
            is_admin=False,
        )
        await session.commit()
    except Exception:
        await session.rollback()

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "provuser", "password": "ProvUser@123"},
    )
    return resp.json()["access_token"]


async def _create_active_account(session: AsyncSession) -> int:
    from app.core.security import encrypt
    from app.repositories.account_repo import AccountRepository

    repo = AccountRepository(session)
    account = await repo.create(
        name="test-account",
        access_key_id=encrypt("AKIATEST123456"),
        secret_access_key=encrypt("secret-key-test"),
        sso_region="us-east-1",
        kiro_region="us-east-1",
        instance_arn="arn:aws:sso:::instance/ssoins-test1234567890",
        identity_store_id="d-1234567890",
        status="active",
    )
    await session.commit()
    return account.id


# ── 请求体校验（422）────────────────────────────────────────────────────────


class TestProvisioningRequestValidation:
    async def test_missing_domain_returns_422(
        self, client: AsyncClient, session: AsyncSession
    ):
        """domain 字段缺失应返回 422，不应返回 200。"""
        token = await _login_admin(client, session)
        account_id = await _create_active_account(session)

        resp = await client.post(
            f"/api/v1/accounts/{account_id}/provisioning",
            json={
                "prefix": "kiro",
                "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 1}],
                # domain 故意缺失
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_legacy_plan_field_returns_422(
        self, client: AsyncClient, session: AsyncSession
    ):
        """使用旧字段名 'plan' 应返回 422（复现并防止本次 bug 回归）。"""
        token = await _login_admin(client, session)
        account_id = await _create_active_account(session)

        resp = await client.post(
            f"/api/v1/accounts/{account_id}/provisioning",
            json={
                "prefix": "kiro",
                "domain": "example.com",
                "plans": [{"plan": "KIRO_ENTERPRISE_PRO", "count": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_empty_plans_returns_422(
        self, client: AsyncClient, session: AsyncSession
    ):
        token = await _login_admin(client, session)
        account_id = await _create_active_account(session)

        resp = await client.post(
            f"/api/v1/accounts/{account_id}/provisioning",
            json={"prefix": "kiro", "domain": "example.com", "plans": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_count_zero_returns_422(
        self, client: AsyncClient, session: AsyncSession
    ):
        token = await _login_admin(client, session)
        account_id = await _create_active_account(session)

        resp = await client.post(
            f"/api/v1/accounts/{account_id}/provisioning",
            json={
                "prefix": "kiro",
                "domain": "example.com",
                "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 0}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422


# ── 权限控制 ───────────────────────────────────────────────────────────────


class TestProvisioningPermissions:
    async def test_unauthenticated_returns_401(
        self, client: AsyncClient, session: AsyncSession
    ):
        account_id = await _create_active_account(session)
        resp = await client.post(
            f"/api/v1/accounts/{account_id}/provisioning",
            json={
                "prefix": "kiro",
                "domain": "example.com",
                "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 1}],
            },
        )
        assert resp.status_code == 401

    async def test_nonadmin_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        token = await _login_nonadmin(client, session)
        account_id = await _create_active_account(session)

        resp = await client.post(
            f"/api/v1/accounts/{account_id}/provisioning",
            json={
                "prefix": "kiro",
                "domain": "example.com",
                "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_get_task_nonadmin_returns_403(
        self, client: AsyncClient, session: AsyncSession
    ):
        """非管理员不能读取任务详情."""
        token = await _login_nonadmin(client, session)
        resp = await client.get(
            "/api/v1/provisioning/tasks/1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_get_task_nonexistent_returns_404(
        self, client: AsyncClient, session: AsyncSession
    ):
        token = await _login_admin(client, session)
        resp = await client.get(
            "/api/v1/provisioning/tasks/999999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# ── 账号不存在 / 未验证 → 正确 HTTP 状态（非 200）─────────────────────────


class TestProvisioningAccountGuard:
    async def test_nonexistent_account_returns_error_before_200(
        self, client: AsyncClient, session: AsyncSession
    ):
        """账号不存在时应在 SSE 流开始前返回错误状态码。"""
        token = await _login_admin(client, session)

        resp = await client.post(
            "/api/v1/accounts/999999/provisioning",
            json={
                "prefix": "kiro",
                "domain": "example.com",
                "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code != 200, (
            "账号不存在时不应返回 200，应在流开始前抛出错误"
        )

    async def test_inactive_account_returns_error_before_200(
        self, client: AsyncClient, session: AsyncSession
    ):
        """未验证账号（status != active）应在 SSE 流开始前返回错误。"""
        from app.core.security import encrypt
        from app.repositories.account_repo import AccountRepository

        repo = AccountRepository(session)
        account = await repo.create(
            name="inactive-account",
            access_key_id=encrypt("AKIATEST"),
            secret_access_key=encrypt("secret"),
            sso_region="us-east-1",
            kiro_region="us-east-1",
            instance_arn="arn:aws:sso:::instance/ssoins-inactive",
            identity_store_id="d-0000000000",
            status="pending",
        )
        await session.commit()

        token = await _login_admin(client, session)
        resp = await client.post(
            f"/api/v1/accounts/{account.id}/provisioning",
            json={
                "prefix": "kiro",
                "domain": "example.com",
                "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 1}],
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code != 200


# ── SSE 流正常返回 ─────────────────────────────────────────────────────────


class TestProvisioningSSEFlow:
    async def test_correct_payload_returns_sse_stream(
        self, client: AsyncClient, session: AsyncSession
    ):
        """正确 payload + mock AWS → 返回 200 text/event-stream，最终事件含 success_count."""
        token = await _login_admin(client, session)
        account_id = await _create_active_account(session)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.user_id = "aws-user-id-001"

        with (
            patch(
                "app.services.user_service.UserService.create_user",
                new_callable=AsyncMock,
                return_value=mock_user,
            ),
            patch(
                "app.services.subscription_service.SubscriptionService.assign",
                new_callable=AsyncMock,
            ),
        ):
            resp = await client.post(
                f"/api/v1/accounts/{account_id}/provisioning",
                json={
                    "prefix": "kiro",
                    "domain": "example.com",
                    "plans": [{"subscription_type": "KIRO_ENTERPRISE_PRO", "count": 1}],
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        # 解析 SSE 事件
        events = []
        for line in resp.text.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        assert len(events) > 0
        final = events[-1]
        assert final["status"] in ("completed", "failed")
        assert "success_count" in final
        assert "failed_count" in final
