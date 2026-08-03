"""Restoran endpointlari (restaurant roli talab qilinadi)."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.models.enums import OfferStatus, Role
from app.models.offer import Offer
from app.models.order import Order, OrderItem
from app.models.product import DailyPrice, Product
from app.models.restaurant import Restaurant
from app.models.user import User
from app.schemas.restaurant import (
    CatalogItemOut,
    OrderDetailOut,
    OrderIn,
    OrderItemOut,
    OrderOut,
)
from app.services.invoice import generate_invoice_pdf
from app.services.order import OrderService

router = APIRouter(tags=["restaurant"])

restaurant_only = require_role(Role.restaurant)


def _order_to_out(order: Order, names: dict) -> OrderOut:
    return OrderOut(
        id=str(order.id),
        delivery_date=order.delivery_date,
        delivery_slot=order.delivery_slot,
        status=order.status,
        total_sum=order.total_sum,
        payment_type=order.payment_type,
        created_at=order.created_at,
        items=[
            OrderItemOut(
                product_id=str(i.product_id),
                product_name=names.get(i.product_id, ""),
                kg=i.kg,
                sell_price_per_kg=i.sell_price_per_kg,
                subtotal=i.subtotal,
            )
            for i in order.items
        ],
    )


async def _product_names(db: AsyncSession, order: Order) -> dict:
    ids = [i.product_id for i in order.items]
    if not ids:
        return {}
    rows = (
        await db.execute(select(Product.id, Product.name_uz).where(Product.id.in_(ids)))
    ).all()
    return {pid: name for pid, name in rows}


@router.get("/catalog", response_model=list[CatalogItemOut])
async def catalog(
    date_q: date = Query(..., alias="date"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(restaurant_only),
):
    """Berilgan yetkazish sanasi uchun katalog: narx + mavjud kg + dehqon soni."""
    price_rows = (
        await db.execute(
            select(Product, DailyPrice)
            .join(DailyPrice, DailyPrice.product_id == Product.id)
            .where(DailyPrice.date == date_q)
        )
    ).all()

    # shu sanaga qabul qilingan e'lonlar: mahsulot bo'yicha kg yig'indisi va dehqon soni
    offer_rows = (
        await db.execute(
            select(
                Offer.product_id,
                func.coalesce(func.sum(Offer.kg), 0),
                func.count(func.distinct(Offer.farmer_id)),
            )
            .where(
                Offer.date == date_q,
                Offer.status.in_([OfferStatus.auto_approved, OfferStatus.approved]),
            )
            .group_by(Offer.product_id)
        )
    ).all()
    avail = {pid: (kg, cnt) for pid, kg, cnt in offer_rows}

    result = []
    for product, price in price_rows:
        kg, cnt = avail.get(product.id, (0, 0))
        result.append(
            CatalogItemOut(
                product_id=str(product.id),
                name_uz=product.name_uz,
                emoji=product.emoji,
                unit=product.unit.value,
                sell_price=price.sell_price,
                available_kg=int(kg),
                farmer_count=int(cnt),
            )
        )
    return result


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(restaurant_only),
):
    try:
        order = await OrderService(db).create_order(
            restaurant_id=user.id,
            items=payload.items,
            delivery_date=payload.delivery_date,
            payment_type=payload.payment_type,
            delivery_slot=payload.delivery_slot,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    names = await _product_names(db, order)
    return _order_to_out(order, names)


@router.get("/orders/mine", response_model=list[OrderOut])
async def my_orders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(restaurant_only),
):
    orders = (
        (
            await db.execute(
                select(Order)
                .where(Order.restaurant_id == user.id)
                .order_by(Order.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    result = []
    for order in orders:
        names = await _product_names(db, order)
        result.append(_order_to_out(order, names))
    return result


async def _get_own_order(db: AsyncSession, order_id: str, user: User) -> Order:
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="order_id noto'g'ri")
    order = await db.get(Order, oid)
    if order is None or order.restaurant_id != user.id:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    return order


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def order_detail(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(restaurant_only),
):
    order = await _get_own_order(db, order_id, user)
    names = await _product_names(db, order)
    base = _order_to_out(order, names)
    return OrderDetailOut(
        **base.model_dump(), timeline=OrderService.build_timeline(order.status)
    )


@router.post("/orders/{order_id}/reorder", response_model=OrderOut, status_code=201)
async def reorder(
    order_id: str,
    delivery_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(restaurant_only),
):
    source = await _get_own_order(db, order_id, user)
    try:
        order = await OrderService(db).reorder(user.id, source, delivery_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    names = await _product_names(db, order)
    return _order_to_out(order, names)


@router.get("/orders/{order_id}/invoice")
async def order_invoice(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(restaurant_only),
):
    order = await _get_own_order(db, order_id, user)
    names = await _product_names(db, order)
    rest = await db.get(Restaurant, user.id)
    pdf = generate_invoice_pdf(order, rest.name if rest else "Restoran", names)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="invoice-{order.id}.pdf"'
        },
    )
