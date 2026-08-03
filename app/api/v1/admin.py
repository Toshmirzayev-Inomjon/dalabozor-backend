"""Admin endpointlari (admin roli talab qilinadi).

Eslatma: prod'da bu qism qo'shimcha 2FA bilan himoyalanadi (sayt admin subdomeni).
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.models.enums import OfferStatus, OrderStatus, Role, Source
from app.models.offer import Offer
from app.models.order import Order, OrderItem
from app.models.product import DailyPrice, PriceCorridor, Product
from app.models.route import Route, RouteStop
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminSetRoleIn,
    AdminUserOut,
    CallOfferIn,
    CorridorProductOut,
    CorridorTodayOut,
    DashboardOut,
    ReviewActionIn,
    ReviewOfferOut,
    RunResult,
    SetCorridorIn,
)
from app.services.allocation import AllocationService
from app.services.auth import (
    AuthService,
    MultipleRoleError,
    ProtectedRoleRemovalError,
    RoleNotAssignedError,
)
from app.services.corridor import PriceCorridorService
from app.services.payout import PayoutService
from app.services.sms import SmsService

router = APIRouter(prefix="/admin", tags=["admin"])

admin_only = require_role(Role.admin)


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)):
    today = date.today()

    # bugungi sotuv (delivery_date = bugun, bekor qilinmagan)
    revenue = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total_sum), 0)).where(
                Order.delivery_date == today, Order.status != OrderStatus.cancelled
            )
        )
    ).scalar()

    # marja: order_item sell - product buy (shu sanadagi daily_price)
    margin_rows = (
        await db.execute(
            select(OrderItem.kg, OrderItem.sell_price_per_kg, DailyPrice.buy_price)
            .join(Order, Order.id == OrderItem.order_id)
            .join(
                DailyPrice,
                (DailyPrice.product_id == OrderItem.product_id)
                & (DailyPrice.date == today),
            )
            .where(Order.delivery_date == today, Order.status != OrderStatus.cancelled)
        )
    ).all()
    margin = sum(kg * (sell - buy) for kg, sell, buy in margin_rows)

    collect_kg = (
        await db.execute(
            select(func.coalesce(func.sum(RouteStop.planned_kg), 0))
            .join(Route, Route.id == RouteStop.route_id)
            .where(Route.date == today)
        )
    ).scalar()

    active = (
        await db.execute(
            select(func.count(Order.id)).where(
                Order.delivery_date == today,
                Order.status.notin_([OrderStatus.paid, OrderStatus.cancelled]),
            )
        )
    ).scalar()

    return DashboardOut(
        date=today,
        revenue=int(revenue),
        margin=int(margin),
        collect_kg=int(collect_kg),
        active_orders=int(active),
    )


@router.get("/corridor/today", response_model=CorridorTodayOut)
async def corridor_today(
    target: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    day = target or date.today()

    products = (await db.execute(select(Product))).scalars().all()
    corridors = {
        c.product_id: c
        for c in (
            await db.execute(select(PriceCorridor).where(PriceCorridor.date == day))
        )
        .scalars()
        .all()
    }
    # e'lon statistikasi
    stat_rows = (
        await db.execute(
            select(
                Offer.product_id,
                func.count(Offer.id),
                func.count(Offer.id).filter(Offer.status == OfferStatus.needs_review),
            )
            .where(Offer.date == day)
            .group_by(Offer.product_id)
        )
    ).all()
    stats = {pid: (total, nr) for pid, total, nr in stat_rows}

    prod_out = []
    for p in products:
        c = corridors.get(p.id)
        total, nr = stats.get(p.id, (0, 0))
        prod_out.append(
            CorridorProductOut(
                product_id=str(p.id),
                name_uz=p.name_uz,
                min_price=c.min_price if c else None,
                max_price=c.max_price if c else None,
                offers_total=total,
                needs_review=nr,
            )
        )

    # ko'rib chiqish kerak bo'lgan e'lonlar
    review_rows = (
        await db.execute(
            select(Offer, User.full_name, Product.name_uz)
            .join(User, User.id == Offer.farmer_id)
            .join(Product, Product.id == Offer.product_id)
            .where(Offer.date == day, Offer.status == OfferStatus.needs_review)
            .order_by(Offer.created_at.desc())
        )
    ).all()
    review_out = [
        ReviewOfferOut(
            id=str(o.id),
            farmer_name=fname,
            product_name=pname,
            kg=o.kg,
            price_per_kg=o.price_per_kg,
            status=o.status,
        )
        for o, fname, pname in review_rows
    ]

    return CorridorTodayOut(date=day, products=prod_out, review_offers=review_out)


@router.post("/corridor/{product_id}", response_model=RunResult)
async def set_corridor(
    product_id: str,
    payload: SetCorridorIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="product_id noto'g'ri")
    if payload.min_price > payload.max_price:
        raise HTTPException(status_code=400, detail="min_price > max_price")

    existing = (
        await db.execute(
            select(PriceCorridor).where(
                PriceCorridor.product_id == pid, PriceCorridor.date == payload.date
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.min_price = payload.min_price
        existing.max_price = payload.max_price
    else:
        db.add(
            PriceCorridor(
                product_id=pid,
                date=payload.date,
                min_price=payload.min_price,
                max_price=payload.max_price,
            )
        )
    await db.flush()
    return RunResult(detail={"product_id": product_id, "date": str(payload.date)})


@router.post("/offers/{offer_id}/review", response_model=RunResult)
async def review_offer(
    offer_id: str,
    payload: ReviewActionIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    try:
        oid = uuid.UUID(offer_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="offer_id noto'g'ri")
    offer = await db.get(Offer, oid)
    if offer is None:
        raise HTTPException(status_code=404, detail="E'lon topilmadi")
    if payload.action == "approve":
        offer.status = OfferStatus.approved
    elif payload.action == "reject":
        offer.status = OfferStatus.rejected
    else:
        raise HTTPException(status_code=400, detail="action: approve | reject")
    await db.flush()
    return RunResult(detail={"offer_id": offer_id, "status": offer.status.value})


@router.get("/routes", response_model=RunResult)
async def admin_routes(
    target: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    day = target or date.today()
    routes = (await db.execute(select(Route).where(Route.date == day))).scalars().all()
    data = []
    for r in routes:
        stops = (
            (await db.execute(select(RouteStop).where(RouteStop.route_id == r.id)))
            .scalars()
            .all()
        )
        data.append(
            {
                "route_id": str(r.id),
                "status": r.status.value,
                "collector_id": str(r.collector_id) if r.collector_id else None,
                "stops": len(stops),
                "planned_kg": sum(s.planned_kg for s in stops),
                "actual_kg": sum(s.actual_kg or 0 for s in stops),
            }
        )
    return RunResult(detail={"date": str(day), "routes": data})


@router.get("/calls", response_model=list[ReviewOfferOut])
async def call_offers(
    db: AsyncSession = Depends(get_db), _: User = Depends(admin_only)
):
    """Qo'ng'iroq orqali kelgan e'lonlar (source=call)."""
    rows = (
        await db.execute(
            select(Offer, User.full_name, Product.name_uz)
            .join(User, User.id == Offer.farmer_id)
            .join(Product, Product.id == Offer.product_id)
            .where(Offer.source == Source.call)
            .order_by(Offer.created_at.desc())
            .limit(100)
        )
    ).all()
    return [
        ReviewOfferOut(
            id=str(o.id),
            farmer_name=fname,
            product_name=pname,
            kg=o.kg,
            price_per_kg=o.price_per_kg,
            status=o.status,
        )
        for o, fname, pname in rows
    ]


@router.post("/calls/offer", response_model=RunResult, status_code=201)
async def create_call_offer(
    payload: CallOfferIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Operator dehqon nomidan e'lon kiritadi (source=call) + tasdiq SMS."""
    try:
        pid = uuid.UUID(payload.product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="product_id noto'g'ri")
    if await db.get(Product, pid) is None:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")

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
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu raqam boshqa rol bilan ro'yxatdan o'tgan — dehqon roli biriktirib bo'lmaydi",
        )

    offer_status = await PriceCorridorService(db).evaluate(
        pid, payload.date, payload.price_per_kg
    )
    offer = Offer(
        farmer_id=farmer_user.id,
        product_id=pid,
        date=payload.date,
        kg=payload.kg,
        price_per_kg=payload.price_per_kg,
        status=offer_status,
        source=Source.call,
    )
    db.add(offer)
    await db.flush()

    await SmsService(db).send(
        payload.farmer_phone,
        f"DalaBozor: {payload.kg} kg e'loningiz qabul qilindi ({payload.price_per_kg} so'm/kg).",
    )
    return RunResult(detail={"offer_id": str(offer.id), "status": offer.status.value})


@router.post("/payouts/run", response_model=RunResult)
async def run_payouts(
    target: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    result = await PayoutService(db).run(target or date.today())
    return RunResult(detail=result)


@router.post("/allocation/run", response_model=RunResult)
async def run_allocation(
    target: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Qo'lda taqsimot (odatda 21:00 cron)."""
    result = await AllocationService(db).run(target or date.today())
    return RunResult(detail=result)


async def _admin_user_out(db: AsyncSession, user: User) -> AdminUserOut:
    await db.refresh(user, attribute_names=["roles"])
    return AdminUserOut(
        id=str(user.id),
        phone=user.phone,
        full_name=user.full_name,
        region=user.region,
        roles=user.role_names,
    )


@router.get("/users", response_model=list[AdminUserOut])
async def admin_users(
    role: Role | None = None,
    q: str = "",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Foydalanuvchilar ro'yxati (rol va qidiruv bo'yicha filter)."""
    stmt = select(User)
    if role is not None:
        stmt = stmt.join(UserRole, UserRole.user_id == User.id).where(
            UserRole.role == role
        )
    q = q.strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(User.phone.ilike(like), User.full_name.ilike(like)))
    stmt = stmt.order_by(User.phone.asc()).limit(200)
    users = (await db.execute(stmt)).scalars().all()
    return [await _admin_user_out(db, u) for u in users]


@router.post("/users/{user_id}/role", response_model=AdminUserOut)
async def admin_assign_role(
    user_id: str,
    payload: AdminSetRoleIn,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    """Admin istalgan rol (admin, collector, farmer, restaurant) biriktiradi.

    Bitta akkaunt — bitta rol: rolga ega foydalanuvchiga ikkinchi rol
    biriktirish mumkin emas (409 qaytariladi).
    """
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id noto'g'ri")
    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    try:
        await AuthService(db).add_role(user, payload.role)
    except MultipleRoleError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return await _admin_user_out(db, user)


@router.delete("/users/{user_id}/role/{role}", response_model=AdminUserOut)
async def admin_remove_role(
    user_id: str,
    role: Role,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_only),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id noto'g'ri")
    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    try:
        await AuthService(db).remove_role(user, role)
    except ProtectedRoleRemovalError:
        raise HTTPException(
            status_code=403, detail="Admin rolini olib tashlab bo'lmaydi"
        )
    except RoleNotAssignedError:
        raise HTTPException(
            status_code=404, detail="Rol foydalanuvchiga biriktirilmagan"
        )
    return await _admin_user_out(db, user)
