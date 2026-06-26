"""FastAPI 应用入口 + 统一异常处理."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.exceptions import KiroFleetError, MFAChallengeRequired
from app.core.logging import setup_logging
from app.core.metrics import metrics

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动 → 初始化 DB → 创建管理员 → 启动调度器."""
    setup_logging()
    logger.info("kiro-fleet starting up...")

    # 开发环境允许从 metadata 建表；生产必须由部署流程执行 alembic upgrade head。
    from app.core.config import get_settings

    if not get_settings().is_production:
        from app.core.db import init_db

        await init_db()

    # 确保初始管理员存在
    from app.core.db import get_session_maker

    async with get_session_maker()() as session:
        from app.services.auth_service import AuthService

        auth_svc = AuthService(session)
        await auth_svc.ensure_initial_admin()
        await session.commit()

    # 启动调度器
    from app.workers.scheduler import start_scheduler

    await start_scheduler()

    logger.info("kiro-fleet ready.")
    yield

    # 关闭时停止调度器和数据库连接池
    from app.workers.scheduler import stop_scheduler

    await stop_scheduler()

    from app.core.db import close_db

    await close_db()
    logger.info("kiro-fleet shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Kiro Fleet",
        description="AWS Identity Center 用户与 Kiro 订阅管理平台",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_observability(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            metrics.record_request(request.url.path, 500)
            logger.exception("request_failed request_id=%s path=%s", request_id, request.url.path)
            raise
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        metrics.record_request(request.url.path, response.status_code)
        logger.info(
            "request_completed request_id=%s method=%s path=%s status=%d duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    # ── 统一异常处理 ──────────────────────────────────────────────────────

    @app.exception_handler(KiroFleetError)
    async def domain_exception_handler(request: Request, exc: KiroFleetError):
        if isinstance(exc, MFAChallengeRequired):
            return JSONResponse(
                status_code=202,
                content={
                    "mfa_required": True,
                    "pre_auth_token": exc.pre_auth_token,
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误"}},
        )

    # ── 注册路由 ──────────────────────────────────────────────────────────

    from app.api.v1 import accounts, auth, credits, logs, provisioning, subscriptions, users

    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(accounts.router, prefix=api_prefix)
    app.include_router(users.router, prefix=api_prefix)
    app.include_router(subscriptions.router, prefix=api_prefix)
    app.include_router(provisioning.router, prefix=api_prefix)
    app.include_router(credits.router, prefix=api_prefix)
    app.include_router(logs.router, prefix=api_prefix)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "kiro-fleet"}

    @app.get("/ready")
    async def ready():
        from app.core.db import get_session_maker

        async with get_session_maker()() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "service": "kiro-fleet"}

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics():
        return PlainTextResponse(
            metrics.render_prometheus(), media_type="text/plain; version=0.0.4"
        )

    return app


app = create_app()
