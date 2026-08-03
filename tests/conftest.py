"""Pytest fikstura'lari — ASGI transport orqali app'ni sinaydi (dev Postgres kerak).

Ishga tushirish:
    docker compose up -d && alembic upgrade head && python -m app.seed
    pytest
"""

import os

os.environ["TESTING"] = "1"  # app importidan OLDIN — NullPool yoqiladi

import random  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import Role  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

API = "/api/v1"


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def rand_phone() -> str:
    return "+99890" + "".join(random.choices("0123456789", k=7))


async def auth_headers(
    client: AsyncClient, phone: str, role: str | None = None
) -> dict:
    await client.post(f"{API}/auth/request-otp", json={"phone": phone})
    r = await client.post(
        f"{API}/auth/verify-otp", json={"phone": phone, "code": "1111"}
    )
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    if role in {"admin", "collector"}:
        # Operatsion rollar self-service API orqali berilmaydi. Himoyalangan
        # endpointlarni test qilish uchun rolni ishonchli setup'da beramiz.
        async with SessionLocal() as db:
            user = (
                await db.execute(select(User).where(User.phone == phone))
            ).scalar_one()
            db.add(UserRole(user_id=user.id, role=Role(role)))
            await db.commit()
    elif role:
        r = await client.post(
            f"{API}/auth/select-role", json={"role": role}, headers=headers
        )
        assert r.status_code == 200, r.text
    return headers
