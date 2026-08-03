"""Test uchun boshlang'ich ma'lumot: katalog, foydalanuvchilar va demo marshrut.

Ishga tushirish:  python -m app.seed
"""
import asyncio
from datetime import date

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.enums import Category, PaymentType, Role, Source, Tariff, Unit
from app.models.farmer import Farmer
from app.models.product import DailyPrice, Product
from app.models.restaurant import Restaurant
from app.models.route import Route, RouteStop
from app.models.user import User, UserRole

PRODUCTS = [
    ("Pomidor", Unit.kg, Category.sabzavot, "🍅", 4300, 5200),
    ("Bodring", Unit.kg, Category.sabzavot, "🥒", 3800, 4600),
    ("Kartoshka", Unit.kg, Category.sabzavot, "🥔", 3200, 3900),
    ("Olma", Unit.kg, Category.meva, "🍎", 6000, 7200),
    ("Ko'katlar", Unit.bogʻlam, Category.kokat, "🌿", 1500, 2000),
]

FARMERS = [
    ("+998900000001", "Akmal Dehqonov", "Qarshi", "Chiroqchi", 39.0334, 66.5721),
    ("+998900000002", "Botir Fermerov", "Qarshi", "Koson", 39.0375, 65.5850),
    ("+998900000003", "Davron Yerchiyev", "Qarshi", "Chiroqchi", 39.0258, 66.5607),
    ("+998900000004", "Erkin Bog'bonov", "Qarshi", "Muborak", 39.2550, 65.1520),
    ("+998900000005", "Farrux Sabzavotov", "Qarshi", "Koson", 39.0452, 65.5974),
]

DEMO_PLANNED_KG = [120, 95, 80, 110, 70]

RESTAURANTS = [
    ("+998911000001", "Osh Markazi", "Qarshi sh., Mustaqillik 12", 38.86, 65.79),
    ("+998911000002", "Milliy Taomlar", "Qarshi sh., Nasaf 44", 38.87, 65.80),
    ("+998911000003", "Choyxona №1", "Qarshi sh., Bunyodkor 7", 38.85, 65.78),
]

COLLECTOR = ("+998922000001", "Yodgor Yig'uvchi", "Qarshi")
ADMIN = ("+998933000001", "Admin Boshqaruvchi", "Toshkent")


async def _get_or_create_user(db, phone, full_name, region) -> User:
    user = (
        await db.execute(select(User).where(User.phone == phone))
    ).scalar_one_or_none()
    if user is None:
        user = User(phone=phone, full_name=full_name, region=region)
        db.add(user)
        await db.flush()
    return user


async def _add_role(db, user, role: Role) -> None:
    exists = (
        await db.execute(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role == role)
        )
    ).scalar_one_or_none()
    if exists is None:
        db.add(UserRole(user_id=user.id, role=role))
        await db.flush()


async def seed() -> None:
    today = date.today()
    async with SessionLocal() as db:
        # --- Mahsulotlar + bugungi narx ---
        product_map = {}
        for name, unit, cat, emoji, buy, sell in PRODUCTS:
            product = (
                await db.execute(select(Product).where(Product.name_uz == name))
            ).scalar_one_or_none()
            if product is None:
                product = Product(name_uz=name, unit=unit, category=cat, emoji=emoji)
                db.add(product)
                await db.flush()
            product_map[name] = product

            price = (
                await db.execute(
                    select(DailyPrice).where(
                        DailyPrice.product_id == product.id, DailyPrice.date == today
                    )
                )
            ).scalar_one_or_none()
            if price is None:
                db.add(
                    DailyPrice(
                        product_id=product.id,
                        date=today,
                        buy_price=buy,
                        sell_price=sell,
                    )
                )

        # --- Dehqonlar ---
        farmer_ids = []
        for phone, name, region, village, geo_lat, geo_lng in FARMERS:
            user = await _get_or_create_user(db, phone, name, region)
            farmer_ids.append(user.id)
            await _add_role(db, user, Role.farmer)
            farmer = await db.get(Farmer, user.id)
            if farmer is None:
                farmer = Farmer(user_id=user.id, village=village, source=Source.app)
                db.add(farmer)
            # Seed qayta ishga tushirilganda foydalanuvchi tanlagan haqiqiy joyni
            # bosib ketmaymiz; faqat koordinatasiz demo profilni to'ldiramiz.
            if farmer.geo_lat is None or farmer.geo_lng is None:
                farmer.geo_lat = geo_lat
                farmer.geo_lng = geo_lng

        # --- Restoranlar ---
        for phone, name, address, lat, lng in RESTAURANTS:
            user = await _get_or_create_user(db, phone, name, "Qarshi")
            await _add_role(db, user, Role.restaurant)
            rest = await db.get(Restaurant, user.id)
            if rest is None:
                db.add(
                    Restaurant(
                        user_id=user.id,
                        name=name,
                        address=address,
                        geo_lat=lat,
                        geo_lng=lng,
                        payment_type=PaymentType.cash,
                        tariff=Tariff.start,
                    )
                )

        # --- Yig'uvchi ---
        cphone, cname, cregion = COLLECTOR
        collector = await _get_or_create_user(db, cphone, cname, cregion)
        await _add_role(db, collector, Role.collector)

        # --- Bugungi demo marshrut ---
        # Mavjud real/test stoplarni o'chirmaymiz. Demo dehqonlar marshrutda yo'q
        # bo'lsa, idempotent tarzda oxiriga qo'shamiz — xarita va qabul oqimini
        # yangi o'rnatmada darhol tekshirish mumkin bo'ladi.
        route = (
            await db.execute(
                select(Route).where(
                    Route.date == today,
                    Route.collector_id == collector.id,
                )
            )
        ).scalars().first()
        if route is None:
            route = Route(date=today, collector_id=collector.id)
            db.add(route)
            await db.flush()

        existing_stops = (
            await db.execute(
                select(RouteStop).where(RouteStop.route_id == route.id)
            )
        ).scalars().all()
        existing_farmer_ids = {stop.farmer_id for stop in existing_stops}
        next_seq = max((stop.seq for stop in existing_stops), default=0) + 1
        for farmer_id, planned_kg in zip(farmer_ids, DEMO_PLANNED_KG, strict=True):
            if farmer_id in existing_farmer_ids:
                continue
            db.add(
                RouteStop(
                    route_id=route.id,
                    farmer_id=farmer_id,
                    seq=next_seq,
                    planned_kg=planned_kg,
                )
            )
            next_seq += 1

        # --- Admin ---
        aphone, aname, aregion = ADMIN
        admin = await _get_or_create_user(db, aphone, aname, aregion)
        await _add_role(db, admin, Role.admin)

        await db.commit()
    print("✅ Seed tayyor: katalog, 5 dehqon, 3 restoran, yig'uvchi, admin va demo marshrut")


if __name__ == "__main__":
    asyncio.run(seed())
