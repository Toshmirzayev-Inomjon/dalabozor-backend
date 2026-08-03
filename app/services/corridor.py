"""Narx koridori xizmati — koridor hisoblash va offer narxini tekshirish."""
from datetime import date as date_type, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import OfferStatus
from app.models.offer import Offer
from app.models.product import PriceCorridor


class PriceCorridorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_corridor(
        self, product_id, target_date: date_type
    ) -> PriceCorridor | None:
        """Berilgan sana uchun koridorni oladi."""
        stmt = select(PriceCorridor).where(
            PriceCorridor.product_id == product_id,
            PriceCorridor.date == target_date,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def ensure_corridor(
        self, product_id, target_date: date_type
    ) -> PriceCorridor:
        """Koridor bo'lmasa, kechagi qabul qilingan offer'lar o'rtachasi ±% dan yaratadi.

        Kechagi ma'lumot bo'lmasa, keng standart koridor (0..10^9) qaytaradi —
        ya'ni barcha narx `auto_approved` bo'ladi (seed/boshlang'ich holat).
        """
        existing = await self.get_corridor(product_id, target_date)
        if existing:
            return existing

        yesterday = target_date - timedelta(days=1)
        avg_price = (
            await self.db.execute(
                select(func.avg(Offer.price_per_kg)).where(
                    Offer.product_id == product_id,
                    Offer.date == yesterday,
                    Offer.status.in_(
                        [OfferStatus.auto_approved, OfferStatus.approved]
                    ),
                )
            )
        ).scalar()

        pct = settings.corridor_percent / 100.0
        if avg_price:
            avg = float(avg_price)
            corridor = PriceCorridor(
                product_id=product_id,
                date=target_date,
                min_price=int(avg * (1 - pct)),
                max_price=int(avg * (1 + pct)),
            )
        else:
            # boshlang'ich: cheksiz koridor
            corridor = PriceCorridor(
                product_id=product_id,
                date=target_date,
                min_price=0,
                max_price=10**9,
            )
        self.db.add(corridor)
        await self.db.flush()
        return corridor

    async def evaluate(
        self, product_id, target_date: date_type, price_per_kg: int
    ) -> OfferStatus:
        """Narx koridor ichida bo'lsa auto_approved, aks holda needs_review."""
        corridor = await self.ensure_corridor(product_id, target_date)
        if corridor.min_price <= price_per_kg <= corridor.max_price:
            return OfferStatus.auto_approved
        return OfferStatus.needs_review
