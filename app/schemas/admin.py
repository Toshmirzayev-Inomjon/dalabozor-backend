"""Admin sxemalari."""

from datetime import date as date_type

from pydantic import BaseModel, Field

from app.models.enums import OfferStatus, Role


class AdminUserOut(BaseModel):
    id: str
    phone: str
    full_name: str | None = None
    region: str | None = None
    roles: list[str] = []


class AdminSetRoleIn(BaseModel):
    role: Role


class DashboardOut(BaseModel):
    date: date_type
    revenue: int  # bugungi sotuv (sell)
    margin: int  # sof marja (sell - buy)
    collect_kg: int  # yig'iladigan kg (reja)
    active_orders: int


class CorridorProductOut(BaseModel):
    product_id: str
    name_uz: str
    min_price: int | None = None
    max_price: int | None = None
    offers_total: int
    needs_review: int


class ReviewOfferOut(BaseModel):
    id: str
    farmer_name: str | None = None
    product_name: str
    kg: int
    price_per_kg: int
    status: OfferStatus


class CorridorTodayOut(BaseModel):
    date: date_type
    products: list[CorridorProductOut] = []
    review_offers: list[ReviewOfferOut] = []


class SetCorridorIn(BaseModel):
    date: date_type
    min_price: int = Field(..., ge=0)
    max_price: int = Field(..., ge=0)


class ReviewActionIn(BaseModel):
    action: str  # approve | reject


class CallOfferIn(BaseModel):
    farmer_phone: str = Field(..., min_length=7, max_length=20)
    product_id: str
    date: date_type
    kg: int = Field(..., gt=0)
    price_per_kg: int = Field(..., gt=0)


class RunResult(BaseModel):
    ok: bool = True
    detail: dict = {}
