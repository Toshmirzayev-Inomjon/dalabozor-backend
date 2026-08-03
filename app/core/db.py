"""Async SQLAlchemy 2.0 sozlamasi: engine, session, Base."""
import os
from collections.abc import AsyncGenerator
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Test rejimida (pytest har test uchun yangi event loop ochadi) ulanish pool'i
# loop'lar orasida qayta ishlatilmasligi uchun NullPool ishlatamiz.
_testing = os.getenv("TESTING") == "1"

_engine_kwargs: dict = {"echo": settings.debug and not _testing}
if _testing:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_pre_ping"] = True

engine = create_async_engine(settings.database_url, **_engine_kwargs)

SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Barcha modellar uchun asosiy klass."""


class TimestampMixin:
    """created_at ustunini beruvchi mixin."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: har so'rov uchun DB sessiya."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
