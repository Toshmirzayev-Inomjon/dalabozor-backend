"""Buyurtma xizmati: order yaratish, reorder, timeline."""
import uuid
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrderStatus, PaymentType
from app.models.order import Order, OrderItem
from app.models.product import DailyPrice, Product
from app.schemas.restaurant import OrderItemIn, TimelineStep

# Buyurtma holati bosqichlari (timeline uchun tartib)
_STATUS_FLOW = [
    (OrderStatus.new, "Qabul qilindi"),
    (OrderStatus.allocated, "Taqsimlandi"),
    (OrderStatus.collecting, "Yig'ilmoqda"),
    (OrderStatus.in_transit, "Yo'lda"),
    (OrderStatus.delivered, "Yetkazildi"),
    (OrderStatus.paid, "To'landi"),
]


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _sell_price(self, product_id: uuid.UUID, target: date_type) -> int:
        """Sotish narxini daily_prices dan oladi (sana bo'yicha)."""
        price = (
            await self.db.execute(
                select(DailyPrice.sell_price).where(
                    DailyPrice.product_id == product_id, DailyPrice.date == target
                )
            )
        ).scalar_one_or_none()
        if price is None:
            raise ValueError("Bu sanaga mahsulot narxi belgilanmagan")
        return price

    async def create_order(
        self,
        restaurant_id: uuid.UUID,
        items: list[OrderItemIn],
        delivery_date: date_type,
        payment_type: PaymentType,
        delivery_slot: str | None = None,
    ) -> Order:
        order = Order(
            restaurant_id=restaurant_id,
            delivery_date=delivery_date,
            delivery_slot=delivery_slot,
            payment_type=payment_type,
            status=OrderStatus.new,
            total_sum=0,
        )
        self.db.add(order)
        await self.db.flush()

        total = 0
        for item in items:
            try:
                product_id = uuid.UUID(item.product_id)
            except ValueError:
                raise ValueError(f"product_id noto'g'ri: {item.product_id}")
            product = await self.db.get(Product, product_id)
            if product is None:
                raise ValueError(f"Mahsulot topilmadi: {item.product_id}")

            price = await self._sell_price(product_id, delivery_date)
            subtotal = price * item.kg
            total += subtotal
            self.db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product_id,
                    kg=item.kg,
                    sell_price_per_kg=price,
                    subtotal=subtotal,
                )
            )

        order.total_sum = total
        await self.db.flush()
        await self.db.refresh(order)
        return order

    async def reorder(
        self, restaurant_id: uuid.UUID, source_order: Order, delivery_date: date_type
    ) -> Order:
        """Mavjud buyurtma elementlarini yangi sanaga takrorlaydi (narx yangilanadi)."""
        items = [
            OrderItemIn(product_id=str(i.product_id), kg=i.kg)
            for i in source_order.items
        ]
        return await self.create_order(
            restaurant_id,
            items,
            delivery_date,
            source_order.payment_type,
            source_order.delivery_slot,
        )

    @staticmethod
    def build_timeline(status: OrderStatus) -> list[TimelineStep]:
        if status == OrderStatus.cancelled:
            return [
                TimelineStep(
                    key="cancelled", label="Bekor qilindi", done=True, current=True
                )
            ]
        current_idx = next(
            (i for i, (s, _) in enumerate(_STATUS_FLOW) if s == status), 0
        )
        steps = []
        for i, (s, label) in enumerate(_STATUS_FLOW):
            steps.append(
                TimelineStep(
                    key=s.value,
                    label=label,
                    done=i < current_idx,
                    current=i == current_idx,
                )
            )
        return steps
