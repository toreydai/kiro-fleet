"""单一配置来源 — 全局只通过 get_settings() 访问."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 安全密钥 ──────────────────────────────────────────────────────────
    SECRET_KEY: str = "your-secret-key-placeholder"
    ENCRYPTION_KEY: str = "your-encryption-key-placeholder"

    # ── JWT ───────────────────────────────────────────────────────────────
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PRE_AUTH_TOKEN_EXPIRE_MINUTES: int = 5
    ALGORITHM: str = "HS256"

    # ── 数据库 ────────────────────────────────────────────────────────────
    # Compose 默认使用本地 MySQL；SQLite 仅保留给隔离测试和轻量开发。
    DB_TYPE: Literal["sqlite", "mysql"] = "mysql"
    SQLITE_PATH: str = "./data/kiro_fleet.db"

    MYSQL_HOST: str = "mysql"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "kiro"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "kiro_fleet"

    # ── 应用 ──────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    # 逗号分隔的浏览器来源。开发期可用 localhost，生产环境必须显式配置。
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    DATA_DIR: str = "./data"
    EXPORTS_DIR: str = "./data/exports"

    # ── IAM Identity Center Trusted Token Issuer ──────────────────────────
    # 服务持有私钥，运行时为每个用户动态签发 JWT，再以 IAM 身份换取 IdC access token。
    SSO_OIDC_CLIENT_ID: str = ""          # IdC Application ARN
    SSO_OIDC_PRIVATE_KEY_B64: str = ""   # RSA 2048 私钥 PEM base64 编码
    SSO_OIDC_ISSUER_URL: str = ""        # JWT iss 声明，必须与 TTI IssuerUrl 一致
    SSO_OIDC_AUDIENCE: str = "kiro-fleet"  # JWT aud，必须在 TTI AuthorizedAudiences 内
    SSO_OIDC_KEY_ID: str = "kiro-fleet-tti-key-1"  # JWKS kid
    SSO_OIDC_REQUESTED_TOKEN_TYPE: str = (
        "urn:ietf:params:aws:token-type:iam_identity_center:access_token"
    )

    # ── Scheduler ────────────────────────────────────────────────────────
    SYNC_INTERVAL_MINUTES: int = 10
    PENDING_RETRY_INTERVAL_MINUTES: int = 10

    # ── 初始管理员 ────────────────────────────────────────────────────────
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "Admin@12345"
    INITIAL_ADMIN_EMAIL: str = "admin@example.com"

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        # 校验在 get_settings() 中集中做，这里只做格式检查
        return v

    @property
    def database_url(self) -> str:
        if self.DB_TYPE == "sqlite":
            path = self.SQLITE_PATH
            # 确保目录存在
            dir_path = os.path.dirname(os.path.abspath(path))
            os.makedirs(dir_path, exist_ok=True)
            abs_path = os.path.abspath(path)
            return f"sqlite+aiosqlite:///{abs_path}"
        else:
            return (
                f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
                f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    for key in ("SECRET_KEY", "ENCRYPTION_KEY"):
        val = getattr(s, key)
        if val.startswith("your-"):
            raise RuntimeError(
                f"[kiro-fleet] 启动失败：{key} 未配置（当前值以 'your-' 开头），"
                "请在 .env 中设置真实密钥后再启动。"
            )
    if s.is_production and (not s.cors_origins or "*" in s.cors_origins):
        raise RuntimeError("[kiro-fleet] 生产环境必须配置非通配符 CORS_ORIGINS")
    if s.is_production and s.INITIAL_ADMIN_PASSWORD == "Admin@12345":
        raise RuntimeError("[kiro-fleet] 生产环境必须修改 INITIAL_ADMIN_PASSWORD")
    if s.DB_TYPE == "mysql" and not s.MYSQL_PASSWORD:
        raise RuntimeError("[kiro-fleet] DB_TYPE=mysql 时必须设置 MYSQL_PASSWORD")
    # 确保导出目录存在
    os.makedirs(s.EXPORTS_DIR, exist_ok=True)
    os.makedirs(s.DATA_DIR, exist_ok=True)
    return s
