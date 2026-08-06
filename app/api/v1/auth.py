"""Auth endpointlari: OTP orqali parolsiz kirish."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import RateLimitExceeded
from app.core.security import (
    JWTError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.telegram import validate_init_data
from app.models.enums import Role
from app.models.farmer import Farmer
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.auth import (
    FarmerProfileOut,
    MeOut,
    ProfileIn,
    RefreshIn,
    RequestOtpIn,
    RequestOtpOut,
    SelectRoleIn,
    TelegramLoginIn,
    TelegramLoginOut,
    TokenOut,
    VerifyOtpIn,
    WebAppLoginIn,
)
from app.services.auth import AuthService, MultipleRoleError

router = APIRouter(prefix="/auth", tags=["auth"])


async def _me_out(db: AsyncSession, user: User) -> MeOut:
    """Barcha auth endpointlari uchun bir xil profil javobini tayyorlaydi."""
    await db.refresh(user, attribute_names=["roles"])
    farmer = await db.get(Farmer, user.id)
    farmer_profile = None
    if farmer is not None:
        farmer_profile = FarmerProfileOut(
            village=farmer.village,
            geo_lat=farmer.geo_lat,
            geo_lng=farmer.geo_lng,
        )
    return MeOut(
        id=str(user.id),
        phone=user.phone,
        full_name=user.full_name,
        region=user.region,
        roles=user.role_names,
        farmer_profile=farmer_profile,
    )


@router.post("/request-otp", response_model=RequestOtpOut)
async def request_otp(payload: RequestOtpIn, db: AsyncSession = Depends(get_db)):
    try:
        code = await AuthService(db).request_otp(payload.phone)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(int(max(e.retry_after, 1)))},
        )
    dev_code = (
        code if settings.env == "dev" or settings.sms_provider != "eskiz" else None
    )
    return RequestOtpOut(sent=True, dev_code=dev_code)


@router.post("/verify-otp", response_model=TokenOut)
async def verify_otp(payload: VerifyOtpIn, db: AsyncSession = Depends(get_db)):
    try:
        user, is_new = await AuthService(db).verify_otp(payload.phone, payload.code)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return TokenOut(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        is_new_user=is_new,
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(payload: RefreshIn, db: AsyncSession = Depends(get_db)):
    """Eski access token tugaganida refresh token bilan yangi juftlik beradi."""
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError("refresh token emas")
        user_id = uuid.UUID(data["sub"])
    except (JWTError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token yaroqsiz"
        )
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Foydalanuvchi topilmadi"
        )
    return TokenOut(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        is_new_user=False,
    )


@router.post("/telegram", response_model=TelegramLoginOut)
async def telegram_login(
    payload: TelegramLoginIn,
    x_bot_secret: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Bot ishonchli login: contact orqali olingan raqam bilan (SMS'siz).

    Faqat bot chaqiradi — `X-Bot-Secret` sarlavhasi bilan himoyalangan.
    """
    if x_bot_secret != settings.bot_api_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Bot secret noto'g'ri"
        )
    user, is_new = await AuthService(db).telegram_login(
        payload.phone, payload.full_name, payload.telegram_id
    )
    return TelegramLoginOut(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        is_new_user=is_new,
        roles=user.role_names,
    )


@router.post("/telegram-webapp", response_model=TelegramLoginOut)
async def telegram_webapp_login(
    payload: WebAppLoginIn,
    db: AsyncSession = Depends(get_db),
):
    """Telegram Mini App login: initData HMAC tekshiriladi (bot tokeni bilan).

    Foydalanuvchi avval botda /start bosib raqamini ulagan bo'lishi kerak
    (telegram_id shu paytda saqlanadi).
    """
    data = validate_init_data(payload.init_data, settings.bot_token)
    user_info = data.get("user") if data else None
    if isinstance(user_info, dict):
        tg_id = user_info.get("id")
    else:
        tg_id = None
    if not isinstance(tg_id, int) and not (isinstance(tg_id, str) and tg_id.isdigit()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="initData yaroqsiz"
        )

    user = await AuthService(db).get_by_telegram_id(int(tg_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avval botda /start bosib raqamingizni ulang",
        )
    return TelegramLoginOut(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        is_new_user=False,
        roles=user.role_names,
    )


@router.post("/select-role", response_model=MeOut)
async def select_role(
    payload: SelectRoleIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bitta akkaunt — bitta rol: foydalanuvchi rolni faqat bir marta tanlaydi.

    Rol tanlanganidan keyin uni o'zgartirish yoki ikkinchi rol qo'shish
    mumkin emas; boshqa rollarni faqat tizim administratori biriktiradi.
    """
    if payload.role not in {Role.farmer, Role.restaurant}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu rolni faqat tizim administratori biriktiradi",
        )
    if user.role_names:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu akkauntda rol allaqachon mavjud — ikkinchi rol qo'shib bo'lmaydi",
        )
    try:
        await AuthService(db).add_role(user, payload.role)
    except MultipleRoleError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return await _me_out(db, user)


@router.post("/profile", response_model=MeOut)
async def update_profile(
    payload: ProfileIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Profil ma'lumotlarini yangilaydi (ism, hudud + rolga xos maydonlar)."""
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.region is not None:
        user.region = payload.region

    # Dehqon profili: maydon yuborilmagan bo'lsa eski qiymat saqlanadi;
    # explicit null qishloq yoki koordinata juftligini tozalaydi.
    farmer_fields = {"village", "geo_lat", "geo_lng"}.intersection(
        payload.model_fields_set
    )
    if farmer_fields:
        farmer = await db.get(Farmer, user.id)
        if farmer is not None:
            if "village" in farmer_fields:
                farmer.village = payload.village
            if "geo_lat" in farmer_fields:
                farmer.geo_lat = payload.geo_lat
                farmer.geo_lng = payload.geo_lng
    # restoran → nom + manzil
    if payload.name is not None or payload.address is not None:
        rest = await db.get(Restaurant, user.id)
        if rest is not None:
            if payload.name is not None:
                rest.name = payload.name
            if payload.address is not None:
                rest.address = payload.address

    await db.flush()
    return await _me_out(db, user)


@router.get("/me", response_model=MeOut)
async def me(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _me_out(db, user)
