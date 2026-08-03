"""Autentifikatsiyalangan AI suhbat endpointlari."""

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.ai import AIStatusOut, ChatIn, ChatOut
from app.services.ai import ROLE_SECTIONS, AIService, AIServiceError

router = APIRouter(prefix="/ai", tags=["ai"])


def get_ai_service() -> AIService:
    return AIService()


def _handle_service_error(exc: AIServiceError) -> NoReturn:
    raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/status", response_model=AIStatusOut)
async def ai_status(
    _user: User = Depends(get_current_user),
    service: AIService = Depends(get_ai_service),
):
    """Kalitlarni oshkor qilmasdan AI imkoniyatlari sozlanganini ko'rsatadi."""
    return AIStatusOut(**service.status())


@router.post("/chat", response_model=ChatOut)
async def ai_chat(
    payload: ChatIn,
    user: User = Depends(get_current_user),
    service: AIService = Depends(get_ai_service),
):
    active_role = payload.active_role.value if payload.active_role else None
    if active_role is not None and active_role not in user.role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Faol rol foydalanuvchiga tegishli emas",
        )
    if payload.active_section is not None and (
        active_role is None
        or payload.active_section not in ROLE_SECTIONS.get(active_role, set())
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Joriy bo'lim faol rolga tegishli emas",
        )
    try:
        return await service.chat(
            payload,
            user_roles=user.role_names,
            active_role=active_role,
            active_section=payload.active_section,
        )
    except AIServiceError as exc:
        _handle_service_error(exc)
