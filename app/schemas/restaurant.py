"""Restoran (order + katalog) sxemalari."""
from datetime import date as date_type, datetime

from pydantic import BaseModel, Field

from app.models.enums import OrderStatus, PaymentType


class CatalogItemOut(BaseModel):
    product_id: str
    name_uz: str
    emoji: str | None = None
    unit: str
    sell_price: int
    available_kg: int      # shu sanaga qabul qilingan e'lonlar yig'indisi
    farmer_count: int      # nechta dehqon taklif qilgan


class OrderItemIn(BaseModel):
    product_id: str
    kg: int = Field(..., gt=0)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(..., min_length=1)
    delivery_date: date_type
    payment_type: PaymentType = PaymentType.cash
    delivery_slot: str | None = None


class OrderItemOut(BaseModel):
    product_id: str
    product_name: str
    kg: int
    sell_price_per_kg: int
    subtotal: int


class OrderOut(BaseModel):
    id: str
    delivery_date: date_type
    delivery_slot: str | None = None
    status: OrderStatus
    total_sum: int
    payment_type: PaymentType
    created_at: datetime
    items: list[OrderItemOut] = []


class TimelineStep(BaseModel):
    key: str
    label: str
    done: bool
    current: bool


class OrderDetailOut(OrderOut):
    timeline: list[TimelineStep] = []
