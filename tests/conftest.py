"""pytest 配置与 fixtures."""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# 使用内存 SQLite 测试
os.environ.setdefault("DB_TYPE", "sqlite")
os.environ.setdefault("SQLITE_PATH", ":memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-1234567890ab")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-testing-only-12345")
os.environ.setdefault("DATA_DIR", "/tmp/kiro-fleet-test")
os.environ.setdefault("EXPORTS_DIR", "/tmp/kiro-fleet-test/exports")


from app.core.config import get_settings

# 清除 lru_cache 让测试使用覆写的 env
get_settings.cache_clear()

# Ensure Base.metadata contains every mapped table before create_all().
import app.models  # noqa: E402, F401
from app.core.db import Base  # noqa: E402

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        # SQLite :memory: is per connection. Reuse one connection so sessions
        # used by the HTTP dependency see the fixture's schema and data.
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """每个测试前后清空限速器，防止进程级单例在测试间积累计数。"""
    from app.core.rate_limit import login_limiter
    login_limiter._requests.clear()
    yield
    login_limiter._requests.clear()


@pytest_asyncio.fixture
async def session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    # Keep tests independent: endpoints intentionally commit their own sessions.
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(test_engine, session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """测试用 HTTP 客户端，使用 ASGI transport."""
    from app.core import db as db_module
    from app.core.db import get_session
    from app.main import app as fastapi_app

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    async def override_get_session():
        async with session_factory() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    # 覆盖 FastAPI DI 依赖
    fastapi_app.dependency_overrides[get_session] = override_get_session

    # 同时替换直接调用 get_session_maker() 的内部服务（如 provisioning_service），
    # 确保它们也使用 test_engine 的同一 SQLite 内存库。
    orig_engine = db_module._engine
    orig_maker = db_module._session_maker
    db_module._engine = test_engine
    db_module._session_maker = session_factory

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()
    db_module._engine = orig_engine
    db_module._session_maker = orig_maker
