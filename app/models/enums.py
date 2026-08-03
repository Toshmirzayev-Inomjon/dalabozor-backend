"""Domen enum'lari — Postgres enum sifatida ham ishlatiladi."""
import enum


class Role(str, enum.Enum):
    farmer = "farmer"
    restaurant = "restaurant"
    collector = "collector"
    admin = "admin"


class Source(str, enum.Enum):
    """E'lon/ro'yxatga olish kanali."""
    app = "app"
    bot = "bot"
    call = "call"
    collector = "collector"


class Unit(str, enum.Enum):
    kg = "kg"
    dona = "dona"
    bogʻlam = "bogʻlam"


class Category(str, enum.Enum):
    sabzavot = "sabzavot"
    meva = "meva"
    kokat = "kokat"


class OfferStatus(str, enum.Enum):
    auto_approved = "auto_approved"
    needs_review = "needs_review"
    approved = "approved"
    rejected = "rejected"


class OrderStatus(str, enum.Enum):
    new = "new"
    allocated = "allocated"
    collecting = "collecting"
    in_transit = "in_transit"
    delivered = "delivered"
    paid = "paid"
    cancelled = "cancelled"


class PaymentType(str, enum.Enum):
    cash = "cash"
    card = "card"
    credit = "credit"


class Tariff(str, enum.Enum):
    start = "start"
    business = "business"
    premium = "premium"


class RouteStatus(str, enum.Enum):
    planned = "planned"
    active = "active"
    done = "done"


class StopStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    skipped = "skipped"


class Quality(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class CardProvider(str, enum.Enum):
    payme = "payme"
    click = "click"


class PaymentKind(str, enum.Enum):
    payout = "payout"
    invoice = "invoice"


class PaymentMethod(str, enum.Enum):
    card = "card"
    cash = "cash"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
