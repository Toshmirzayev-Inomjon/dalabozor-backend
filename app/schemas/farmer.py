"""Dehqon (farmer) sxemalari."""
from datetime import date as date_type

from pydantic import BaseModel, Field

from app.models.enums import OfferStatus, Source


class PriceTodayOut(BaseModel):
    product_id: str
    name_uz: str
    emoji: str | None = None
    unit: str
    buy_price: int
    # kechagiga nisbatan o'zgarish (foiz), bo'lmasa None
    change_pct: float | None = None


class OfferIn(BaseModel):
    product_id: str
    date: date_type
    kg: int = Field(..., gt=0)
    price_per_kg: int = Field(..., gt=0)
    source: Source = Source.app


class OfferOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    date: date_type
    kg: int
    price_per_kg: int
    status: OfferStatus
    source: Source
    estimated_income: int  # kg * price_per_kg


class BalanceOut(BaseModel):
    month_kg: int
    month_sum: int
    last_payout: int | None = None
    rating: float
