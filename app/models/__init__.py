"""Barcha modellarni yagona joyda import qilamiz — Alembic metadata to'liq ko'rishi uchun."""
from app.core.db import Base
from app.models.enums import (
    Category,
    CardProvider,
    OfferStatus,
    OrderStatus,
    PaymentKind,
    PaymentMethod,
    PaymentStatus,
    PaymentType,
    Quality,
    Role,
    RouteStatus,
    Source,
    StopStatus,
    Tariff,
    Unit,
)
from app.models.farmer import Farmer
from app.models.offer import Offer
from app.models.order import Order, OrderItem
from app.models.payment import Card, Payment
from app.models.product import DailyPrice, PriceCorridor, Product
from app.models.restaurant import Restaurant
from app.models.route import Allocation, Route, RouteStop
from app.models.user import OtpCode, SmsLog, User, UserRole

__all__ = [
    "Base",
    "User",
    "UserRole",
    "OtpCode",
    "SmsLog",
    "Farmer",
    "Restaurant",
    "Product",
    "PriceCorridor",
    "DailyPrice",
    "Offer",
    "Order",
    "OrderItem",
    "Allocation",
    "Route",
    "RouteStop",
    "Card",
    "Payment",
    "Role",
    "Source",
    "Unit",
    "Category",
    "OfferStatus",
    "OrderStatus",
    "PaymentType",
    "Tariff",
    "RouteStatus",
    "StopStatus",
    "Quality",
    "CardProvider",
    "PaymentKind",
    "PaymentMethod",
    "PaymentStatus",
]
