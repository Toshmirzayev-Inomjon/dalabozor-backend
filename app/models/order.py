"""Restoran buyurtmasi va band elementlari."""
import uuid
from datetime import date as date_type

from sqlalchemy import (
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.models.enums import OrderStatus, PaymentType


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_date_status", "delivery_date", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.user_id", ondelete="CASCADE"), nullable=False
    )
    delivery_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    delivery_slot: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.new, nullable=False
    )
    total_sum: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type"), default=PaymentType.cash, nullable=False
    )

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    kg: Mapped[int] = mapped_column(Integer, nullable=False)
    sell_price_per_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product = relationship("Product", lazy="selectin")
