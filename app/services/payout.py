"""PayoutService — 12:00 cron.

Qabul qilingan (accepted) to'xtashlar bo'yicha: actual_kg × dehqonning o'rtacha
taklif narxi → payout. PaymentService orqali (mock) o'tkaziladi.
"""

from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderStatus, PaymentStatus, StopStatus
from app.models.offer import Offer
from app.models.order import Order, OrderItem
from app.models.route import Allocation, Route, RouteStop
from app.services.payment import PaymentService


class PayoutService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _farmer_avg_price(self, farmer_id, target_date: date_type) -> float:
        """Dehqonning shu sanadagi taqsimlangan e'lonlari bo'yicha o'rtacha (og'irlik) narx."""
        rows = (
            await self.db.execute(
                select(Allocation.kg, Offer.price_per_kg)
                .join(Offer, Offer.id == Allocation.offer_id)
                .where(Offer.farmer_id == farmer_id, Offer.date == target_date)
            )
        ).all()
        total_kg = sum(kg for kg, _ in rows)
        if total_kg == 0:
            return 0.0
        total_val = sum(kg * price for kg, price in rows)
        return total_val / total_kg

    async def run(self, target_date: date_type) -> dict:
        """Bugungi marshrutlarning accepted stop'lari bo'yicha payout."""
        routes = (
            (await self.db.execute(select(Route).where(Route.date == target_date)))
            .scalars()
            .all()
        )
        payment_service = PaymentService(self.db)
        total_paid = 0
        count = 0

        for route in routes:
            stops = (
                (
                    await self.db.execute(
                        select(RouteStop).where(
                            RouteStop.route_id == route.id,
                            RouteStop.status == StopStatus.accepted,
                            RouteStop.actual_kg.isnot(None),
                            RouteStop.paid.is_(False),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for stop in stops:
                avg_price = await self._farmer_avg_price(stop.farmer_id, target_date)
                amount = round(avg_price * stop.actual_kg)
                if amount <= 0:
                    continue
                payment = await payment_service.payout(stop.farmer_id, amount)
                # Muvaffaqiyatli yoki naqd (pending — operator tasdiqlaydi)
                # holatda stopni 'paid' deb belgilaymiz — takror to'lov bo'lmasligi
                # uchun (12:00 cron + admin qo'lda run ikki marta pul o'tkaza olmaydi).
                if payment.status != PaymentStatus.failed:
                    stop.paid = True
                total_paid += amount
                count += 1

        # yetkazilgan buyurtmalarni 'paid' qilamiz (soddalashtirilgan)
        delivered = (
            (
                await self.db.execute(
                    select(Order).where(
                        Order.delivery_date == target_date,
                        Order.status == OrderStatus.delivered,
                    )
                )
            )
            .scalars()
            .all()
        )
        for order in delivered:
            order.status = OrderStatus.paid
        await self.db.flush()

        return {"payouts": count, "total_paid": total_paid}
