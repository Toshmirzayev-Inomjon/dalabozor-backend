"""Karta va to'lovlar. Karta to'liq raqami/CVV/expiry HECH QACHON saqlanmaydi."""
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin
from app.models.enums import (
    CardProvider,
    PaymentKind,
    PaymentMethod,
    PaymentStatus,
)


class Card(Base, TimestampMixin):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[CardProvider] = mapped_column(
        Enum(CardProvider, name="card_provider"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(500), nullable=False)  # shifrlangan
    last4: Mapped[str | None] = mapped_column(String(4))
    brand: Mapped[str | None] = mapped_column(String(40))


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[PaymentKind] = mapped_column(
        Enum(PaymentKind, name="payment_kind"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL")
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"),
        default=PaymentStatus.pending,
        nullable=False,
    )
    provider_ref: Mapped[str | None] = mapped_column(String(120))
