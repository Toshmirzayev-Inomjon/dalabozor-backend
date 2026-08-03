"""Yig'uvchi endpointlari (collector roli talab qilinadi)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.core.time import today as biz_today
from app.models.enums import Role, Source, StopStatus
from app.models.farmer import Farmer
from app.models.offer import Offer
from app.models.product import Product
from app.models.route import Allocation, Route, RouteStop
from app.models.user import User
from app.schemas.collector import (
    AcceptStopIn,
    AcceptStopOut,
    OnBehalfOfferIn,
    OnBehalfOfferOut,
    RouteOut,
    StopOut,
)
from app.services.auth import AuthService, MultipleRoleError
from app.services.corridor import PriceCorridorService

router = APIRouter(tags=["collector"])

collector_only = require_role(Role.collector)


async def _stop_products(
    db: AsyncSession, farmer_id: uuid.UUID, target: date
) -> list[str]:
    """Shu dehqondan shu sanaga taqsimlangan mahsulot nomlari."""
    rows = (
        await db.execute(
            select(Product.name_uz)
            .join(Offer, Offer.product_id == Product.id)
            .join(Allocation, Allocation.offer_id == Offer.id)
            .where(Offer.farmer_id == farmer_id, Offer.date == target)
            .distinct()
        )
    ).all()
    return [r[0] for r in rows]


@router.get("/routes/today", response_model=RouteOut | None)
async def route_today(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(collector_only),
):
    today = biz_today()
    route = (
        (
            await db.execute(
                select(Route).where(
                    Route.date == today,
                    Route.collector_id == user.id,
                )
            )
        )
        .scalars()
        .first()
    )
    if route is None:
        return None

    stops = (
        await db.execute(
            select(
                RouteStop,
                User.full_name,
                Farmer.village,
                Farmer.geo_lat,
                Farmer.geo_lng,
            )
            .join(Farmer, Farmer.user_id == RouteStop.farmer_id)
            .join(User, User.id == RouteStop.farmer_id)
            .where(RouteStop.route_id == route.id)
            .order_by(RouteStop.seq)
        )
    ).all()

    stop_out = []
    total_planned = 0
    total_actual = 0
    for stop, fname, village, geo_lat, geo_lng in stops:
        total_planned += stop.planned_kg
        total_actual += stop.actual_kg or 0
        stop_out.append(
            StopOut(
                id=str(stop.id),
                seq=stop.seq,
                farmer_id=str(stop.farmer_id),
                farmer_name=fname,
                village=village,
                geo_lat=geo_lat,
                geo_lng=geo_lng,
                planned_kg=stop.planned_kg,
                actual_kg=stop.actual_kg,
                quality=stop.quality,
                status=stop.status,
                products=await _stop_products(db, stop.farmer_id, today),
            )
        )

    return RouteOut(
        id=str(route.id),
        date=route.date,
        status=route.status,
        total_planned_kg=total_planned,
        total_actual_kg=total_actual,
        stops=stop_out,
    )


@router.post("/stops/{stop_id}/accept", response_model=AcceptStopOut)
async def accept_stop(
    stop_id: str,
    payload: AcceptStopIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(collector_only),
):
    try:
        sid = uuid.UUID(stop_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="stop_id noto‘g'ri")

    stop = (
        await db.execute(
            select(RouteStop, Route.date)
            .join(Route, Route.id == RouteStop.route_id)
            .where(
                RouteStop.id == sid,
                Route.collector_id == user.id,
                Route.date == biz_today(),
            )
        )
    ).one_or_none()
    if stop is None:
        raise HTTPException(
            status_code=404,
            detail="To'xtash topilmadi yoki sizga biriktirilmagan",
        )
    stop, route_date = stop

    # Pulni shishirishdan himoya: fakt miqdor rejadan oshib keta olmaydi.
    if payload.actual_kg > stop.planned_kg:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Fakt miqdor rejadan oshib ketishi mumkin emas (reja: {stop.planned_kg} kg)"
            ),
        )

    # To'lov reestriga o'tgan to'xtashni qayta qabul qilish bilan
    # fakt ma'lumotlari soxtalashtirilmasin.
    if stop.paid:
        raise HTTPException(
            status_code=409,
            detail="Bu to'xtash bo'yicha to'lov amalga oshirilgan",
        )

    stop.actual_kg = payload.actual_kg
    stop.quality = payload.quality
    stop.status = StopStatus.accepted
    await db.flush()

    # taxminiy payout (12:00 da haqiqiy o'tkaziladi).
    # Narx marshrut o'z sanasi ("buguni" emas) bo'yicha olinadi.
    from app.services.payout import PayoutService

    avg = await PayoutService(db)._farmer_avg_price(stop.farmer_id, route_date)
    estimated = round(avg * payload.actual_kg)

    return AcceptStopOut(
        id=str(stop.id),
        status=stop.status,
        actual_kg=stop.actual_kg,
        quality=stop.quality,
        estimated_payout=estimated,
    )


@router.post(
    "/offers/on-behalf",
    response_model=OnBehalfOfferOut,
    status_code=status.HTTP_201_CREATED,
)
async def offer_on_behalf(
    payload: OnBehalfOfferIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(collector_only),
):
    """Dehqon nomidan e'lon (source=collector). Dehqon yo'q bo'lsa yaratiladi."""
    try:
        product_id = uuid.UUID(payload.product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="product_id noto'g'ri")
    if await db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

    # dehqonni topamiz yoki yaratamiz
    farmer_user = (
        await db.execute(select(User).where(User.phone == payload.farmer_phone))
    ).scalar_one_or_none()
    if farmer_user is None:
        farmer_user = User(phone=payload.farmer_phone)
        db.add(farmer_user)
        await db.flush()
    try:
        await AuthService(db).add_role(farmer_user, Role.farmer)
    except MultipleRoleError:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bu raqam boshqa rol bilan ro'yxatdan o'tgan — dehqon roli "
                "biriktirib bo'lmaydi"
            ),
        )

    offer_status = await PriceCorridorService(db).evaluate(
        product_id, payload.date, payload.price_per_kg
    )
    offer = Offer(
        farmer_id=farmer_user.id,
        product_id=product_id,
        date=payload.date,
        kg=payload.kg,
        price_per_kg=payload.price_per_kg,
        status=offer_status,
        source=Source.collector,
    )
    db.add(offer)
    await db.flush()

    return OnBehalfOfferOut(
        id=str(offer.id),
        farmer_phone=payload.farmer_phone,
        status=offer.status,
        source=offer.source,
    )
