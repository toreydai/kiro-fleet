"""数据库引擎与 Session 工厂."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.DB_TYPE == "sqlite":
            connect_args = {"check_same_thread": False}
        _engine = create_async_engine(
            settings.database_url,
            echo=not settings.is_production,
            connect_args=connect_args,
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入用的 session 工厂."""
    async with get_session_maker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """创建所有表（用于开发/测试；生产环境应用 Alembic 迁移）."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭引擎连接池."""
    engine = get_engine()
    await engine.dispose()
