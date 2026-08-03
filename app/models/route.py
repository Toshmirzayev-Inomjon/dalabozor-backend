"""Taqsimot (allocation), marshrut va to'xtashlar."""

import uuid
from datetime import date as date_type

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import Quality, RouteStatus, StopStatus


class Allocation(Base):
    """21:00 cron: order_item ni offer ga bog'laydi."""

    __tablename__ = "allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    __table_args__ = (
        # Xuddi shu order que'yi ikkita run'da ikki marta taqsimlanmasligi uchun.
        UniqueConstraint(
            "order_item_id", "offer_id", name="uq_allocations_order_item_offer"
        ),
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), nullable=False
    )
    kg: Mapped[int] = mapped_column(Integer, nullable=False)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    collector_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[RouteStatus] = mapped_column(
        Enum(RouteStatus, name="route_status"),
        default=RouteStatus.planned,
        nullable=False,
    )

    stops: Mapped[list["RouteStop"]] = relationship(
        back_populates="route",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RouteStop.seq",
    )


class RouteStop(Base):
    __tablename__ = "route_stops"
    __table_args__ = (Index("ix_route_stops_route_seq", "route_id", "seq"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farmers.user_id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_kg: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_kg: Mapped[int | None] = mapped_column(Integer)
    quality: Mapped[Quality | None] = mapped_column(Enum(Quality, name="quality"))
    status: Mapped[StopStatus] = mapped_column(
        Enum(StopStatus, name="stop_status"), default=StopStatus.pending, nullable=False
    )
    # Payout idempotentligi: shu to'xtash bo'yicha to'lov reestriga o'tganmi.
    paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    route: Mapped["Route"] = relationship(back_populates="stops")
