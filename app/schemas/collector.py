"""Yig'uvchi (collector) sxemalari."""
from datetime import date as date_type

from pydantic import BaseModel, Field

from app.models.enums import OfferStatus, Quality, RouteStatus, Source, StopStatus


class StopOut(BaseModel):
    id: str
    seq: int
    farmer_id: str
    farmer_name: str | None = None
    village: str | None = None
    geo_lat: float | None = None
    geo_lng: float | None = None
    planned_kg: int
    actual_kg: int | None = None
    quality: Quality | None = None
    status: StopStatus
    products: list[str] = []  # shu dehqondan yig'iladigan mahsulotlar


class RouteOut(BaseModel):
    id: str
    date: date_type
    status: RouteStatus
    total_planned_kg: int
    total_actual_kg: int
    stops: list[StopOut] = []


class AcceptStopIn(BaseModel):
    actual_kg: int = Field(..., ge=0)
    quality: Quality


class AcceptStopOut(BaseModel):
    id: str
    status: StopStatus
    actual_kg: int
    quality: Quality
    estimated_payout: int


class OnBehalfOfferIn(BaseModel):
    farmer_phone: str = Field(..., min_length=7, max_length=20)
    product_id: str
    date: date_type
    kg: int = Field(..., gt=0)
    price_per_kg: int = Field(..., gt=0)


class OnBehalfOfferOut(BaseModel):
    id: str
    farmer_phone: str
    status: OfferStatus
    source: Source
