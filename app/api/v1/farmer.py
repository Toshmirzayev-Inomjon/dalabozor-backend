"""Dehqon endpointlari (farmer roli talab qilinadi)."""
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.models.enums import OfferStatus, PaymentKind, PaymentStatus, Role
from app.models.farmer import Farmer
from app.models.offer import Offer
from app.models.payment import Payment
from app.models.product import DailyPrice, Product
from app.models.user import User
from app.schemas.farmer import (
    BalanceOut,
    OfferIn,
    OfferOut,
    PriceTodayOut,
)
from app.services.corridor import PriceCorridorService

router = APIRouter(tags=["farmer"])

farmer_only = require_role(Role.farmer)


def _offer_to_out(offer: Offer, product_name: str) -> OfferOut:
    return OfferOut(
        id=str(offer.id),
        product_id=str(offer.product_id),
        product_name=product_name,
        date=offer.date,
        kg=offer.kg,
        price_per_kg=offer.price_per_kg,
        status=offer.status,
        source=offer.source,
        estimated_income=offer.kg * offer.price_per_kg,
    )


@router.get("/prices/today", response_model=list[PriceTodayOut])
async def prices_today(db: AsyncSession = Depends(get_db), _: User = Depends(farmer_only)):
    """Bugungi qabul narxlari (ertangi yig'im uchun)."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    rows = (
        await db.execute(
            select(Product, DailyPrice)
            .join(DailyPrice, DailyPrice.product_id == Product.id)
            .where(DailyPrice.date == today)
        )
    ).all()

    # kechagi narxlar (o'zgarishni hisoblash uchun)
    y_prices = {
        pid: bp
        for pid, bp in (
            await db.execute(
                select(DailyPrice.product_id, DailyPrice.buy_price).where(
                    DailyPrice.date == yesterday
                )
            )
        ).all()
    }

    result = []
    for product, price in rows:
        change = None
        y = y_prices.get(product.id)
        if y:
            change = round((price.buy_price - y) / y * 100, 1)
        result.append(
            PriceTodayOut(
                product_id=str(product.id),
                name_uz=product.name_uz,
                emoji=product.emoji,
                unit=product.unit.value,
                buy_price=price.buy_price,
                change_pct=change,
            )
        )
    return result


@router.post("/offers", response_model=OfferOut, status_code=status.HTTP_201_CREATED)
async def create_offer(
    payload: OfferIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(farmer_only),
):
    """E'lon yaratadi — narx koridorini tekshirib status belgilaydi."""
    try:
        product_id = uuid.UUID(payload.product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="product_id noto'g'ri")

    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    offer_status = await PriceCorridorService(db).evaluate(
        product_id, payload.date, payload.price_per_kg
    )
    offer = Offer(
        farmer_id=user.id,
        product_id=product_id,
        date=payload.date,
        kg=payload.kg,
        price_per_kg=payload.price_per_kg,
        status=offer_status,
        source=payload.source,
    )
    db.add(offer)
    await db.flush()
    return _offer_to_out(offer, product.name_uz)


@router.get("/offers/mine", response_model=list[OfferOut])
async def my_offers(
    date_filter: date | None = Query(None, alias="date"),
    status_filter: OfferStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(farmer_only),
):
    stmt = (
        select(Offer, Product.name_uz)
        .join(Product, Product.id == Offer.product_id)
        .where(Offer.farmer_id == user.id)
        .order_by(Offer.created_at.desc())
    )
    if date_filter:
        stmt = stmt.where(Offer.date == date_filter)
    if status_filter:
        stmt = stmt.where(Offer.status == status_filter)

    rows = (await db.execute(stmt)).all()
    return [_offer_to_out(o, name) for o, name in rows]


@router.get("/farmers/me/balance", response_model=BalanceOut)
async def my_balance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(farmer_only),
):
    """Bu oylik topshirilgan kg + summa + oxirgi to'lov."""
    first_day = date.today().replace(day=1)

    # bu oylik qabul qilingan e'lonlar (approx: auto_approved + approved)
    kg, total = (
        await db.execute(
            select(
                func.coalesce(func.sum(Offer.kg), 0),
                func.coalesce(func.sum(Offer.kg * Offer.price_per_kg), 0),
            ).where(
                Offer.farmer_id == user.id,
                Offer.date >= first_day,
                Offer.status.in_([OfferStatus.auto_approved, OfferStatus.approved]),
            )
        )
    ).one()

    last_payout = (
        await db.execute(
            select(Payment.amount)
            .where(
                Payment.user_id == user.id,
                Payment.type == PaymentKind.payout,
                Payment.status == PaymentStatus.success,
            )
            .order_by(Payment.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    rating = (
        await db.execute(select(Farmer.rating).where(Farmer.user_id == user.id))
    ).scalar_one_or_none() or 5.0
    return BalanceOut(
        month_kg=int(kg),
        month_sum=int(total),
        last_payout=last_payout,
        rating=rating,
    )
