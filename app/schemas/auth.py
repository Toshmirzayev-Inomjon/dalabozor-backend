"""Auth Pydantic sxemalari."""

from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models.enums import Role


class RequestOtpIn(BaseModel):
    phone: str = Field(..., examples=["+998901234567"], min_length=7, max_length=20)


class RequestOtpOut(BaseModel):
    sent: bool = True
    # dev'da qulaylik uchun kod qaytariladi (prod'da None)
    dev_code: str | None = None


class VerifyOtpIn(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20)
    code: str = Field(..., min_length=3, max_length=8)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = False


class TelegramLoginIn(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20)
    telegram_id: int
    full_name: str | None = None


class TelegramLoginOut(TokenOut):
    roles: list[str] = []


class WebAppLoginIn(BaseModel):
    init_data: str  # Telegram.WebApp.initData (imzolangan qator)


class RefreshIn(BaseModel):
    refresh_token: str


class ProfileIn(BaseModel):
    full_name: str | None = None
    region: str | None = None
    village: str | None = None  # dehqon
    address: str | None = None  # restoran
    name: str | None = None  # restoran nomi
    geo_lat: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        allow_inf_nan=False,
    )
    geo_lng: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        allow_inf_nan=False,
    )

    @model_validator(mode="after")
    def validate_geo_pair(self) -> Self:
        """Koordinatalar faqat to'liq juftlik sifatida yoziladi yoki tozalanadi."""
        lat_supplied = "geo_lat" in self.model_fields_set
        lng_supplied = "geo_lng" in self.model_fields_set
        if lat_supplied != lng_supplied:
            raise ValueError("geo_lat va geo_lng birga yuborilishi kerak")
        if not lat_supplied:
            return self
        if (self.geo_lat is None) != (self.geo_lng is None):
            raise ValueError(
                "geo_lat va geo_lng ikkalasi ham qiymat yoki null bo'lishi kerak"
            )
        if self.geo_lat == 0 and self.geo_lng == 0:
            raise ValueError("(0, 0) haqiqiy joylashuv sifatida qabul qilinmaydi")
        return self


class SelectRoleIn(BaseModel):
    """Ro'yxatdan o'tishda tanlanadigan yagona rol (keyin o'zgartirib bo'lmaydi)."""

    role: Role


class RoleOut(BaseModel):
    role: Role


class FarmerProfileOut(BaseModel):
    village: str | None = None
    geo_lat: float | None = None
    geo_lng: float | None = None


class RestaurantProfileOut(BaseModel):
    name: str
    address: str | None = None


class MeOut(BaseModel):
    id: str
    phone: str
    full_name: str | None = None
    region: str | None = None
    roles: list[str] = []
    farmer_profile: FarmerProfileOut | None = None
    restaurant_profile: RestaurantProfileOut | None = None
