"""Mahsulot, narx koridori, kunlik narxlar."""
import uuid
from datetime import date as date_type

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import Category, Unit


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name_uz: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[Unit] = mapped_column(
        Enum(Unit, name="unit"), default=Unit.kg, nullable=False
    )
    category: Mapped[Category] = mapped_column(
        Enum(Category, name="category"), nullable=False
    )
    emoji: Mapped[str | None] = mapped_column(String(8))


class PriceCorridor(Base):
    __tablename__ = "price_corridor"
    __table_args__ = (
        UniqueConstraint("product_id", "date", name="uq_corridor_product_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    min_price: Mapped[int] = mapped_column(Integer, nullable=False)
    max_price: Mapped[int] = mapped_column(Integer, nullable=False)


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (
        UniqueConstraint("product_id", "date", name="uq_price_product_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    buy_price: Mapped[int] = mapped_column(Integer, nullable=False)  # dehqondan
    sell_price: Mapped[int] = mapped_column(Integer, nullable=False)  # restoranga
