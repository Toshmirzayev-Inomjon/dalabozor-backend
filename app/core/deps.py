"""FastAPI dependency'lari: joriy user va rol tekshiruvi."""
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import JWTError, decode_token
from app.models.enums import Role
from app.models.user import User

bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT access tokendan joriy foydalanuvchini oladi."""
    try:
        payload = decode_token(creds.credentials)
        if payload.get("type") != "access":
            raise ValueError("access token emas")
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token yaroqsiz yoki muddati o'tgan",
        )

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Foydalanuvchi topilmadi"
        )
    return user


def require_role(*roles: Role):
    """Berilgan rollardan kamida bittasi bo'lishini talab qiladi."""
    allowed = {r.value for r in roles}

    async def checker(user: User = Depends(get_current_user)) -> User:
        if not allowed.intersection(user.role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Ruxsat yo'q — kerakli rol: {', '.join(allowed)}",
            )
        return user

    return checker
