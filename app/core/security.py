"""Xavfsizlik: JWT, hashlash, karta tokenini shifrlash."""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import settings


# --- Hashlash (OTP kodi va h.k.) ---
# OTP — qisqa muddatli raqamli kod; JWT sirini kalit sifatida ishlatib
# HMAC-SHA256 yetarli (bcrypt ortiqcha va sekin).
def hash_secret(raw: str) -> str:
    return hmac.new(
        settings.jwt_secret.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()


def verify_secret(raw: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_secret(raw), hashed)


# --- JWT ---
def _create_token(subject: str, expires: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return _create_token(
        subject, timedelta(minutes=settings.access_token_expire_minutes), "access"
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, timedelta(days=settings.refresh_token_expire_days), "refresh"
    )


def decode_token(token: str) -> dict[str, Any]:
    """Tokenni ochadi; noto'g'ri bo'lsa JWTError ko'taradi."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# --- Karta tokenini shifrlash (Fernet) ---
def _fernet() -> Fernet:
    key = settings.card_encryption_key
    if not key:
        raise RuntimeError("CARD_ENCRYPTION_KEY sozlanmagan")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_token(cipher: str) -> str:
    return _fernet().decrypt(cipher.encode()).decode()


__all__ = [
    "hash_secret",
    "verify_secret",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "encrypt_token",
    "decrypt_token",
    "JWTError",
]
