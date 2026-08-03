"""AllocationService — 21:00 cron.

Buyurtmalarni (order_items) shu sanaga qabul qilingan e'lonlarga (offers) taqsimlaydi,
so'ng qishloq bo'yicha guruhlab marshrut (route + stops) tuzadi.

Sodda algoritm: har order_item uchun mos mahsulot offer'larini
dehqon reytingi bo'yicha (yuqoridan pastga) FIFO taqsimlaydi.
"""

import uuid
from collections import defaultdict
from datetime import date as date_type

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OfferStatus, OrderStatus, Role, StopStatus
from app.models.farmer import Farmer
from app.models.offer import Offer
from app.models.order import Order, OrderItem
from app.models.route import Allocation, Route, RouteStop
from app.models.user import User, UserRole


class AllocationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _remaining_by_offer(self, offer_ids: list[uuid.UUID]) -> dict:
        """Har offer uchun qolgan (taqsimlanmagan) kg."""
        if not offer_ids:
            return {}
        rows = (
            await self.db.execute(
                select(Allocation.offer_id, func.coalesce(func.sum(Allocation.kg), 0))
                .where(Allocation.offer_id.in_(offer_ids))
                .group_by(Allocation.offer_id)
            )
        ).all()
        return {oid: kg for oid, kg in rows}

    async def _allocated_by_item(self, item_ids: list[uuid.UUID]) -> dict:
        """Har order_item hozirgacha necha kg taqsimlangan (re-run xavfsizligi)."""
        if not item_ids:
            return {}
        rows = (
            await self.db.execute(
                select(
                    Allocation.order_item_id,
                    func.coalesce(func.sum(Allocation.kg), 0),
                )
                .where(Allocation.order_item_id.in_(item_ids))
                .group_by(Allocation.order_item_id)
            )
        ).all()
        return {iid: kg for iid, kg in rows}

    async def run(self, target_date: date_type) -> dict:
        """Taqsimotni bajaradi. Natija statistikasini qaytaradi."""
        # 1) Shu sanaga 'new' buyurtmalar
        orders = (
            (
                await self.db.execute(
                    select(Order).where(
                        Order.delivery_date == target_date,
                        Order.status == OrderStatus.new,
                    )
                )
            )
            .scalars()
            .all()
        )
        if not orders:
            return {"orders": 0, "allocated_kg": 0, "stops": 0}

        order_ids = [o.id for o in orders]
        items = (
            (
                await self.db.execute(
                    select(OrderItem).where(OrderItem.order_id.in_(order_ids))
                )
            )
            .scalars()
            .all()
        )
        items_by_order: dict = defaultdict(list)
        for item in items:
            items_by_order[item.order_id].append(item)
        item_ids = [i.id for i in items]
        allocated_by_item = await self._allocated_by_item(item_ids)
        # Qaysi (order_item, offer) juftligi allaqachon taqsimlangan — re-run
        # vaqtida qayta qo'shilsa uq_allocations_order_item_offer buziladi.
        pairs_by_item: dict = defaultdict(set)
        for iid, oid in (
            await self.db.execute(
                select(Allocation.order_item_id, Allocation.offer_id).where(
                    Allocation.order_item_id.in_(item_ids)
                )
            )
        ).all():
            pairs_by_item[iid].add(oid)

        # 2) Shu sanaga mos e'lonlar (mahsulot bo'yicha), reyting bo'yicha tartiblangan
        offers = (
            (
                await self.db.execute(
                    select(Offer)
                    .join(Farmer, Farmer.user_id == Offer.farmer_id)
                    .where(
                        Offer.date == target_date,
                        Offer.status.in_(
                            [OfferStatus.auto_approved, OfferStatus.approved]
                        ),
                    )
                    .order_by(Farmer.rating.desc(), Offer.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        offers_by_product: dict = defaultdict(list)
        for offer in offers:
            offers_by_product[offer.product_id].append(offer)

        remaining = await self._remaining_by_offer([o.id for o in offers])
        offer_remaining = {o.id: o.kg - int(remaining.get(o.id, 0)) for o in offers}

        # 3/4) Taqsimlash + buyurtma holati.
        # Qayta ishga tushirishda avval taqsimlangan kg hisobga olinadi;
        # faqat to'liq ta'minlangan buyurtmalar 'allocated' bo'ladi.
        allocated_kg = 0
        farmer_planned: dict = defaultdict(int)  # farmer_id -> planned kg
        item_satisfied: dict[uuid.UUID, bool] = {
            item.id: int(allocated_by_item.get(item.id, 0)) >= item.kg for item in items
        }
        for item in items:
            need = item.kg - int(allocated_by_item.get(item.id, 0))
            for offer in offers_by_product.get(item.product_id, []):
                if need <= 0:
                    break
                if offer.id in pairs_by_item[item.id]:
                    continue
                avail = offer_remaining.get(offer.id, 0)
                if avail <= 0:
                    continue
                take = min(need, avail)
                self.db.add(
                    Allocation(order_item_id=item.id, offer_id=offer.id, kg=take)
                )
                pairs_by_item[item.id].add(offer.id)
                offer_remaining[offer.id] -= take
                allocated_by_item[item.id] = (
                    int(allocated_by_item.get(item.id, 0)) + take
                )
                farmer_planned[offer.farmer_id] += take
                allocated_kg += take
                need -= take
            if int(allocated_by_item.get(item.id, 0)) >= item.kg:
                item_satisfied[item.id] = True

        for order in orders:
            if all(item_satisfied[item.id] for item in items_by_order[order.id]):
                order.status = OrderStatus.allocated

        await self.db.flush()

        # 5) Marshrut tuzamiz (bitta marshrut, qishloq bo'yicha stop tartibi)
        stops_count = await self._build_route(target_date, farmer_planned)

        return {
            "orders": len(orders),
            "allocated_kg": allocated_kg,
            "stops": stops_count,
        }

    async def _build_route(self, target_date: date_type, farmer_planned: dict) -> int:
        """Dehqonlarni qishloq bo'yicha guruhlab, tartiblangan to'xtashli marshrut yaratadi."""
        if not farmer_planned:
            return 0

        # Eski marshrut(lar)ni faqat ularga ISHLASH BOSHLAQMAGAN bo'lsa tozalaymiz.
        # Qabul qilingan (accepted/skipped yoki actual_kg yozilgan) to'xtashlar
        # o'chirilmaydi — aks holda payout va tablitsa ma'lumotlari yo'qoladi.
        old = (
            (await self.db.execute(select(Route).where(Route.date == target_date)))
            .scalars()
            .all()
        )
        for route in old:
            has_work = (
                await self.db.execute(
                    select(RouteStop.id)
                    .where(
                        RouteStop.route_id == route.id,
                        (RouteStop.status != StopStatus.pending)
                        | (RouteStop.actual_kg.isnot(None)),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if has_work is None:
                await self.db.delete(route)
            else:
                # Ish boshlangan marshrutga aralashmaymiz — yangi qo'shimcha
                # taqsimot stopsiz qoladi, ammo yozilgan faktlar saqlanadi.
                return 0
        await self.db.flush()

        # birinchi yig'uvchini biriktiramiz (bo'lsa)
        collector_id = (
            await self.db.execute(
                select(UserRole.user_id).where(UserRole.role == Role.collector).limit(1)
            )
        ).scalar_one_or_none()

        route = Route(date=target_date, collector_id=collector_id)
        self.db.add(route)
        await self.db.flush()

        # qishloq ma'lumoti
        farmer_ids = list(farmer_planned.keys())
        villages = {
            fid: village
            for fid, village in (
                await self.db.execute(
                    select(Farmer.user_id, Farmer.village).where(
                        Farmer.user_id.in_(farmer_ids)
                    )
                )
            ).all()
        }
        # qishloq bo'yicha saralaymiz — bir qishloq dehqonlari ketma-ket keladi
        ordered = sorted(
            farmer_ids, key=lambda fid: (villages.get(fid) or "", str(fid))
        )

        for seq, fid in enumerate(ordered, start=1):
            self.db.add(
                RouteStop(
                    route_id=route.id,
                    farmer_id=fid,
                    seq=seq,
                    planned_kg=farmer_planned[fid],
                )
            )
        await self.db.flush()
        return len(ordered)
