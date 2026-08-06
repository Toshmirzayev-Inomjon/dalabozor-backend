"""Tizimda kamida bitta admin borligini kafolatlaydi (idempotent).

Ishga tushirish: python -m app.ensure_admin
"""

import asyncio

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.enums import Role
from app.models.user import User, UserRole

ADMIN = ("+998933000001", "Admin Boshqaruvchi", "Toshkent")


async def ensure_admin() -> None:
    phone, full_name, region = ADMIN
    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.phone == phone))
        ).scalar_one_or_none()
        if user is None:
            user = User(phone=phone, full_name=full_name, region=region)
            db.add(user)
            await db.flush()
        exists = (
            await db.execute(
                select(UserRole).where(
                    UserRole.user_id == user.id, UserRole.role == Role.admin
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(UserRole(user_id=user.id, role=Role.admin))
        await db.commit()
        print(f"admin kafolatlandi: {phone}")


if __name__ == "__main__":
    asyncio.run(ensure_admin())
