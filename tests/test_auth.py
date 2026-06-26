"""认证全链路测试."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _create_admin(session: AsyncSession) -> tuple[str, str]:
    """在 session 中创建管理员，返回 (username, password)."""
    from app.services.auth_service import AuthService

    svc = AuthService(session)
    username = "testadmin"
    password = "TestAdmin@123"
    try:
        await svc.create_system_user(
            username=username,
            email="testadmin@example.com",
            password=password,
            is_admin=True,
        )
        await session.commit()
    except Exception:
        await session.rollback()
    return username, password


class TestLogin:
    async def test_login_success(self, client: AsyncClient, session: AsyncSession):
        username, password = await _create_admin(session)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, session: AsyncSession):
        username, _ = await _create_admin(session)
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "wrong-password"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTHENTICATION_FAILED"

    async def test_login_nonexistent_user(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "whatever"},
        )
        assert resp.status_code == 401

    async def test_get_me_with_token(self, client: AsyncClient, session: AsyncSession):
        username, password = await _create_admin(session)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        token = login_resp.json()["access_token"]

        me_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["username"] == username
        assert data["is_admin"] is True

    async def test_get_me_without_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


class TestRefreshToken:
    async def test_refresh_success(self, client: AsyncClient, session: AsyncSession):
        username, password = await _create_admin(session)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        refresh_token = login_resp.json()["refresh_token"]

        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_resp.status_code == 200
        data = refresh_resp.json()
        assert "access_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.refresh.token"},
        )
        assert resp.status_code == 401

    async def test_refresh_revoked_after_use(self, client: AsyncClient, session: AsyncSession):
        """Refresh token 使用一次后应被吊销，再次使用应失败."""
        username, password = await _create_admin(session)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        refresh_token = login_resp.json()["refresh_token"]

        # 第一次使用
        r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r1.status_code == 200

        # 第二次使用同一 token 应失败
        r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r2.status_code == 401


class TestMFA:
    async def test_mfa_setup_and_verify(self, client: AsyncClient, session: AsyncSession):
        username, password = await _create_admin(session)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Setup MFA
        setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert setup_resp.status_code == 200
        secret = setup_resp.json()["secret"]

        # Enable MFA with valid TOTP
        import pyotp

        totp = pyotp.TOTP(secret)
        code = totp.now()

        enable_resp = await client.post(
            "/api/v1/auth/mfa/enable",
            json={"totp_code": code},
            headers=headers,
        )
        assert enable_resp.status_code == 200

    async def test_mfa_disable_requires_totp(self, client: AsyncClient, session: AsyncSession):
        """禁用 MFA 必须提供当前 TOTP code."""
        username, password = await _create_admin(session)
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        setup_resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        secret = setup_resp.json()["secret"]

        import pyotp

        totp = pyotp.TOTP(secret)
        code = totp.now()

        await client.post(
            "/api/v1/auth/mfa/enable",
            json={"totp_code": code},
            headers=headers,
        )

        # 禁用时输入错误 code
        disable_resp = await client.post(
            "/api/v1/auth/mfa/disable",
            json={"totp_code": "000000"},
            headers=headers,
        )
        assert disable_resp.status_code in (400, 422)


class TestSystemUserManagement:
    async def test_delete_last_admin_forbidden(self, client: AsyncClient, session: AsyncSession):
        """不能删除最后一个管理员."""
        # 先确保只有一个 admin
        from app.repositories.user_repo import SystemUserRepository

        repo = SystemUserRepository(session)
        # 创建单独的管理员用于此测试
        from app.services.auth_service import AuthService

        svc = AuthService(session)
        last_admin_name = "last_admin_test"
        try:
            user = await svc.create_system_user(
                username=last_admin_name,
                email="last_admin@test.com",
                password="Admin@123456",
                is_admin=True,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            return

        # 登录为该管理员
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": last_admin_name, "password": "Admin@123456"},
        )
        token = login_resp.json().get("access_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # 如果是唯一管理员，尝试删除自己应被拒绝
        admin_count = await repo.count_admins()
        if admin_count == 1:
            del_resp = await client.delete(f"/api/v1/auth/users/{user.id}", headers=headers)
            assert del_resp.status_code == 400
            data = del_resp.json()
            assert data["error"]["code"] == "LAST_ADMIN"

    async def test_non_admin_cannot_manage_users(self, client: AsyncClient, session: AsyncSession):
        """普通用户无法管理系统用户."""
        from app.services.auth_service import AuthService

        svc = AuthService(session)
        try:
            await svc.create_system_user(
                username="normaluser",
                email="normal@test.com",
                password="Normal@123",
                is_admin=False,
            )
            await session.commit()
        except Exception:
            await session.rollback()

        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "normaluser", "password": "Normal@123"},
        )
        token = login_resp.json().get("access_token", "")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/api/v1/auth/users", headers=headers)
        assert resp.status_code == 403
