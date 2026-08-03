"""To'lov xizmati — adapter orqali charge/payout, karta tokenizatsiya."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.payment import get_payment_adapter
from app.core.security import decrypt_token, encrypt_token
from app.models.enums import (
    CardProvider,
    OrderStatus,
    PaymentKind,
    PaymentMethod,
    PaymentStatus,
)
from app.models.order import Order
from app.models.payment import Card, Payment


class DuplicatePaymentError(Exception):
    """Buyurtma allaqachon muvaffaqiyatli to'langan."""


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.adapter = get_payment_adapter()

    async def start_card_link(self, user_id: uuid.UUID, provider: CardProvider):
        """Karta bog'lash: provayder oynasi. Mock'da tokenni darhol saqlaydi."""
        result = await self.adapter.start_tokenization(str(user_id))
        if result.token:
            card = Card(
                user_id=user_id,
                provider=provider,
                token=encrypt_token(result.token),  # shifrlab saqlaymiz
                last4=result.last4,
                brand=result.brand,
            )
            self.db.add(card)
            await self.db.flush()
        return result

    async def _user_card(self, user_id: uuid.UUID) -> Card | None:
        return (
            (
                await self.db.execute(
                    select(Card)
                    .where(Card.user_id == user_id)
                    .order_by(Card.created_at.desc())
                )
            )
            .scalars()
            .first()
        )

    async def charge_invoice(
        self, user_id: uuid.UUID, order_id: uuid.UUID | None, amount: int
    ) -> Payment:
        """Restoran buyurtmasi to'lovi (token orqali).

        Ikki marta to'lash oldini oladi: order qatorini qulflash va avvalgi
        muvaffaqiyatli invoice mavjudligini tekshirish orqali.
        """
        if order_id is not None:
            order = (
                await self.db.execute(
                    select(Order).where(Order.id == order_id).with_for_update()
                )
            ).scalar_one_or_none()
            if order is None or order.status == OrderStatus.cancelled:
                raise ValueError("Bekor qilingan buyurtmani to'lash mumkin emas")
            already_paid = (
                await self.db.execute(
                    select(Payment.id).where(
                        Payment.order_id == order_id,
                        Payment.type == PaymentKind.invoice,
                        Payment.status == PaymentStatus.success,
                    )
                )
            ).scalar_one_or_none()
            if already_paid is not None:
                raise DuplicatePaymentError("Buyurtma allaqachon to'langan")

        card = await self._user_card(user_id)
        payment = Payment(
            type=PaymentKind.invoice,
            user_id=user_id,
            order_id=order_id,
            amount=amount,
            method=PaymentMethod.card if card else PaymentMethod.cash,
            status=PaymentStatus.pending,
        )
        self.db.add(payment)
        await self.db.flush()

        if card:
            res = await self.adapter.charge(decrypt_token(card.token), amount)
            payment.status = (
                PaymentStatus.success if res.success else PaymentStatus.failed
            )
            payment.provider_ref = res.provider_ref
        else:
            # naqd — keyin operator tasdiqlaydi
            payment.status = PaymentStatus.pending
        await self.db.flush()
        return payment

    async def payout(self, user_id: uuid.UUID, amount: int) -> Payment:
        """Dehqonga pul o'tkazish.

        Foydalanuvchida karta bo'lmasa provayderga MURACYAT qilinmaydi — to'lov
        'pending' (naqd) sifatida yoziladi va operator tasdiqlaydi.
        """
        card = await self._user_card(user_id)
        payment = Payment(
            type=PaymentKind.payout,
            user_id=user_id,
            amount=amount,
            method=PaymentMethod.card if card else PaymentMethod.cash,
            status=PaymentStatus.pending,
        )
        self.db.add(payment)
        await self.db.flush()

        if card:
            res = await self.adapter.payout(decrypt_token(card.token), amount)
            payment.status = (
                PaymentStatus.success if res.success else PaymentStatus.failed
            )
            payment.provider_ref = res.provider_ref
        else:
            # naqd — operator tasdiqlashi kerak, adapter chaqirilmaydi
            payment.status = PaymentStatus.pending
        await self.db.flush()
        return payment
