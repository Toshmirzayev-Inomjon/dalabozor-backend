"""Dehqon profili."""
import uuid

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.enums import Source


class Farmer(Base):
    __tablename__ = "farmers"
    __table_args__ = (
        CheckConstraint(
            "(geo_lat IS NULL) = (geo_lng IS NULL)",
            name="ck_farmers_geo_pair",
        ),
        CheckConstraint(
            "geo_lat IS NULL OR geo_lat BETWEEN -90 AND 90",
            name="ck_farmers_geo_lat_range",
        ),
        CheckConstraint(
            "geo_lng IS NULL OR geo_lng BETWEEN -180 AND 180",
            name="ck_farmers_geo_lng_range",
        ),
        CheckConstraint(
            "geo_lat IS NULL OR NOT (geo_lat = 0 AND geo_lng = 0)",
            name="ck_farmers_geo_not_origin",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    village: Mapped[str | None] = mapped_column(String(120))
    geo_lat: Mapped[float | None] = mapped_column(Float)
    geo_lng: Mapped[float | None] = mapped_column(Float)
    card_token: Mapped[str | None] = mapped_column(String(500))  # shifrlangan
    card_last4: Mapped[str | None] = mapped_column(String(4))
    card_brand: Mapped[str | None] = mapped_column(String(40))
    rating: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    source: Mapped[Source] = mapped_column(
        Enum(Source, name="source"), default=Source.app, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="farmer")


from app.models.user import User  # noqa: E402
