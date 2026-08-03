"""Yig'uvchi faqat o'ziga biriktirilgan marshrutni o'zgartira oladi."""

import uuid
from datetime import date

import sqlalchemy as sa

from app.core.db import SessionLocal
from app.models.route import Route, RouteStop
from tests.conftest import API, auth_headers, rand_phone


async def test_collector_cannot_accept_another_collectors_stop(client):
    owner_headers = await auth_headers(client, rand_phone(), role="collector")
    other_headers = await auth_headers(client, rand_phone(), role="collector")
    farmer_headers = await auth_headers(client, rand_phone(), role="farmer")

    owner = (await client.get(f"{API}/auth/me", headers=owner_headers)).json()
    farmer = (await client.get(f"{API}/auth/me", headers=farmer_headers)).json()

    async with SessionLocal() as db:
        route = Route(date=date.today(), collector_id=uuid.UUID(owner["id"]))
        db.add(route)
        await db.flush()
        stop = RouteStop(
            route_id=route.id,
            farmer_id=uuid.UUID(farmer["id"]),
            seq=1,
            planned_kg=30,
        )
        db.add(stop)
        await db.flush()
        stop_id = str(stop.id)
        await db.commit()

    denied = await client.post(
        f"{API}/stops/{stop_id}/accept",
        json={"actual_kg": 28, "quality": "A"},
        headers=other_headers,
    )
    assert denied.status_code == 404

    accepted = await client.post(
        f"{API}/stops/{stop_id}/accept",
        json={"actual_kg": 28, "quality": "A"},
        headers=owner_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["actual_kg"] == 28

    # Test keyingi testlarga to'sqinlik qilmasligi uchun qabul qilingan
    # stop'ni (va uning marshrutini) tozalaymiz — aks holda allocation
    # "ish boshlangan marshrut" deb bugungi marshrutni tuzolmaydi.
    async with SessionLocal() as db:
        await db.execute(sa.delete(RouteStop).where(RouteStop.route_id == route.id))
        await db.execute(sa.delete(Route).where(Route.id == route.id))
        await db.commit()


async def test_route_today_returns_farmer_coordinates(client):
    collector_headers = await auth_headers(client, rand_phone(), role="collector")
    farmer_headers = await auth_headers(client, rand_phone(), role="farmer")

    collector = (await client.get(f"{API}/auth/me", headers=collector_headers)).json()
    farmer = (await client.get(f"{API}/auth/me", headers=farmer_headers)).json()
    location = await client.post(
        f"{API}/auth/profile",
        json={
            "village": "Qarshi, Xonobod",
            "geo_lat": 38.8612,
            "geo_lng": 65.7897,
        },
        headers=farmer_headers,
    )
    assert location.status_code == 200

    async with SessionLocal() as db:
        route = Route(
            date=date.today(),
            collector_id=uuid.UUID(collector["id"]),
        )
        db.add(route)
        await db.flush()
        db.add(
            RouteStop(
                route_id=route.id,
                farmer_id=uuid.UUID(farmer["id"]),
                seq=1,
                planned_kg=45,
            )
        )
        await db.commit()

    response = await client.get(
        f"{API}/routes/today",
        headers=collector_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["stops"]) == 1
    stop = body["stops"][0]
    assert stop["farmer_id"] == farmer["id"]
    assert stop["village"] == "Qarshi, Xonobod"
    assert stop["geo_lat"] == 38.8612
    assert stop["geo_lng"] == 65.7897
