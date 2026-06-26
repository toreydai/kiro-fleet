"""安全工具：JWT、密码哈希、AES-256-GCM 加密."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 密码 ──────────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────


def _get_secret_key() -> str:
    return get_settings().SECRET_KEY


def create_access_token(
    subject: str | int,
    extra: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _get_secret_key(), algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str | int) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=settings.ALGORITHM)


def create_pre_auth_token(user_id: int) -> str:
    """MFA 挑战令牌，有效期 5 分钟，type=mfa_challenge."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.PRE_AUTH_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "mfa_challenge",
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """解码并验证令牌。返回 payload；若无效则抛 JWTError."""
    settings = get_settings()
    payload = jwt.decode(token, _get_secret_key(), algorithms=[settings.ALGORITHM])
    if payload.get("type") != expected_type:
        raise JWTError(f"令牌类型错误：期望 {expected_type}，实际 {payload.get('type')}")
    return payload


# ── AES-256-GCM 加密 ──────────────────────────────────────────────────────


def _derive_key() -> bytes:
    """从 ENCRYPTION_KEY 派生 32 字节 AES 密钥."""
    raw = get_settings().ENCRYPTION_KEY
    # 用 SHA-256 统一派生，无论输入多长都输出 32 字节
    return hashlib.sha256(raw.encode()).digest()


def encrypt(plaintext: str) -> str:
    """AES-256-GCM 加密，返回 base64(nonce + ciphertext_with_tag)."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(ciphertext_b64: str) -> str:
    """AES-256-GCM 解密."""
    key = _derive_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(ciphertext_b64)
    nonce, ct = raw[:12], raw[12:]
    return aesgcm.decrypt(nonce, ct, None).decode()


def generate_totp_secret() -> str:
    """生成 TOTP 密钥（base32）."""
    import pyotp

    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    """验证 TOTP code（允许 ±1 窗口）."""
    import pyotp

    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def get_totp_uri(secret: str, username: str, issuer: str = "KiroFleet") -> str:
    """生成 TOTP URI（用于二维码）."""
    import pyotp

    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)
