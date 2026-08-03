"""To'lov endpointlari (Billing Hub adapteri orqali)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_role
from app.models.enums import Role
from app.models.order import Order
from app.models.user import User
from app.schemas.payment import (
    CardLinkIn,
    CardLinkOut,
    InvoiceIn,
    PaymentOut,
    PayoutIn,
)
from app.services.payment import DuplicatePaymentError, PaymentService

router = APIRouter(tags=["payment"])


def _payment_out(p) -> PaymentOut:
    return PaymentOut(
        id=str(p.id),
        type=p.type.value,
        amount=p.amount,
        method=p.method.value,
        status=p.status,
        provider_ref=p.provider_ref,
    )


@router.post("/cards", response_model=CardLinkOut)
async def link_card(
    payload: CardLinkIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Karta bog'lash — provayder tokenizatsiya oynasi. Faqat token saqlanadi."""
    res = await PaymentService(db).start_card_link(user.id, payload.provider)
    return CardLinkOut(redirect_url=res.redirect_url, last4=res.last4, brand=res.brand)


@router.post("/payments/invoice", response_model=PaymentOut)
async def pay_invoice(
    payload: InvoiceIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(Role.restaurant)),
):
    try:
        oid = uuid.UUID(payload.order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="order_id noto'g'ri")
    order = await db.get(Order, oid)
    if order is None or order.restaurant_id != user.id:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")

    try:
        payment = await PaymentService(db).charge_invoice(
            user.id, order.id, order.total_sum
        )
    except DuplicatePaymentError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _payment_out(payment)


@router.post("/payments/payout", response_model=PaymentOut)
async def make_payout(
    payload: PayoutIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.admin)),
):
    """Dehqonga pul (odatda cron chaqiradi; admin qo'lda ham bajarishi mumkin)."""
    try:
        fid = uuid.UUID(payload.farmer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="farmer_id noto'g'ri")
    payment = await PaymentService(db).payout(fid, payload.amount)
    return _payment_out(payment)
