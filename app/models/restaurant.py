"""Restoran profili."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import PaymentType, Tariff


class Restaurant(Base):
    __tablename__ = "restaurants"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    geo_lat: Mapped[float | None] = mapped_column(Float)
    geo_lng: Mapped[float | None] = mapped_column(Float)
    credit_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type"), default=PaymentType.cash, nullable=False
    )
    tariff: Mapped[Tariff] = mapped_column(
        Enum(Tariff, name="tariff"), default=Tariff.start, nullable=False
    )
    tariff_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="restaurant")


from app.models.user import User  # noqa: E402
