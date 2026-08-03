"""Dehqon e'loni (offer)."""
import uuid
from datetime import date as date_type

from sqlalchemy import Date, Enum, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin
from app.models.enums import OfferStatus, Source


class Offer(Base, TimestampMixin):
    __tablename__ = "offers"
    __table_args__ = (Index("ix_offers_date_status", "date", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farmers.user_id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)  # yig'im sanasi
    kg: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OfferStatus] = mapped_column(
        Enum(OfferStatus, name="offer_status"), nullable=False
    )
    source: Mapped[Source] = mapped_column(
        Enum(Source, name="source"), default=Source.app, nullable=False
    )

    product = relationship("Product", lazy="selectin")
