"""Auth oqimi testlari."""

import asyncio

import pytest

from app.schemas.auth import ProfileIn
from tests.conftest import API, auth_headers, rand_phone


async def test_request_and_verify_otp(client):
    phone = rand_phone()
    r = await client.post(f"{API}/auth/request-otp", json={"phone": phone})
    assert r.status_code == 200
    assert r.json()["dev_code"] == "1111"

    r = await client.post(
        f"{API}/auth/verify-otp", json={"phone": phone, "code": "1111"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["is_new_user"] is True


async def test_wrong_code_rejected(client):
    phone = rand_phone()
    await client.post(f"{API}/auth/request-otp", json={"phone": phone})
    r = await client.post(
        f"{API}/auth/verify-otp", json={"phone": phone, "code": "0000"}
    )
    assert r.status_code == 400


async def test_me_requires_token(client):
    r = await client.get(f"{API}/auth/me")
    assert r.status_code == 401  # Bearer token yo'q


async def test_select_role_and_me(client):
    phone = rand_phone()
    headers = await auth_headers(client, phone, role="farmer")
    r = await client.get(f"{API}/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["roles"] == ["farmer"]
    assert r.json()["farmer_profile"] == {
        "village": None,
        "geo_lat": None,
        "geo_lng": None,
    }


async def test_farmer_profile_coordinates_can_be_updated_and_cleared(client):
    headers = await auth_headers(client, rand_phone(), role="farmer")

    updated = await client.post(
        f"{API}/auth/profile",
        json={
            "village": "Qarshi, Xonobod",
            "geo_lat": 38.8612,
            "geo_lng": 65.7897,
        },
        headers=headers,
    )

    assert updated.status_code == 200
    assert updated.json()["farmer_profile"] == {
        "village": "Qarshi, Xonobod",
        "geo_lat": 38.8612,
        "geo_lng": 65.7897,
    }
    persisted = await client.get(f"{API}/auth/me", headers=headers)
    assert persisted.status_code == 200
    assert persisted.json()["farmer_profile"] == updated.json()["farmer_profile"]

    cleared = await client.post(
        f"{API}/auth/profile",
        json={"village": None, "geo_lat": None, "geo_lng": None},
        headers=headers,
    )

    assert cleared.status_code == 200
    assert cleared.json()["farmer_profile"] == {
        "village": None,
        "geo_lat": None,
        "geo_lng": None,
    }


async def test_farmer_profile_rejects_partial_and_origin_coordinates(client):
    headers = await auth_headers(client, rand_phone(), role="farmer")

    partial = await client.post(
        f"{API}/auth/profile",
        json={"geo_lat": 38.8612},
        headers=headers,
    )
    origin = await client.post(
        f"{API}/auth/profile",
        json={"geo_lat": 0, "geo_lng": 0},
        headers=headers,
    )

    assert partial.status_code == 422
    assert origin.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"geo_lat": 91, "geo_lng": 65},
        {"geo_lat": 38, "geo_lng": -181},
        {"geo_lat": float("inf"), "geo_lng": 65},
        {"geo_lat": 38, "geo_lng": float("nan")},
    ],
)
def test_profile_schema_rejects_invalid_finite_coordinates(payload):
    with pytest.raises(ValueError):
        ProfileIn.model_validate(payload)


async def test_cannot_select_second_role(client):
    """Bitta akkaunt — bitta rol: ikkinchi (boshqa) rolni tanlab bo'lmaydi."""
    phone = rand_phone()
    headers = await auth_headers(client, phone, role="farmer")

    r = await client.post(
        f"{API}/auth/select-role", json={"role": "restaurant"}, headers=headers
    )

    assert r.status_code == 409
    me = await client.get(f"{API}/auth/me", headers=headers)
    assert me.json()["roles"] == ["farmer"]


async def test_parallel_select_role_is_idempotent(client):
    phone = rand_phone()
    await client.post(f"{API}/auth/request-otp", json={"phone": phone})
    r = await client.post(
        f"{API}/auth/verify-otp", json={"phone": phone, "code": "1111"}
    )
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    first, second = await asyncio.gather(
        client.post(
            f"{API}/auth/select-role", json={"role": "restaurant"}, headers=headers
        ),
        client.post(
            f"{API}/auth/select-role", json={"role": "restaurant"}, headers=headers
        ),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    me = await client.get(f"{API}/auth/me", headers=headers)
    assert me.json()["roles"] == ["restaurant"]


async def test_self_service_admin_role_rejected(client):
    phone = rand_phone()
    headers = await auth_headers(client, phone, role="farmer")

    r = await client.post(
        f"{API}/auth/select-role", json={"role": "admin"}, headers=headers
    )

    assert r.status_code == 403
    me = await client.get(f"{API}/auth/me", headers=headers)
    assert me.json()["roles"] == ["farmer"]


async def test_self_service_collector_role_rejected(client):
    phone = rand_phone()
    headers = await auth_headers(client, phone, role="farmer")

    r = await client.post(
        f"{API}/auth/select-role", json={"role": "collector"}, headers=headers
    )

    assert r.status_code == 403
    me = await client.get(f"{API}/auth/me", headers=headers)
    assert me.json()["roles"] == ["farmer"]


async def test_no_role_remove_self_service_endpoint(client):
    """Self-service rol olib tashlash endpoint'i butunlay olib tashlangan."""
    phone = rand_phone()
    headers = await auth_headers(client, phone, role="farmer")

    r = await client.post(
        f"{API}/auth/remove-role", json={"role": "farmer"}, headers=headers
    )

    assert r.status_code == 404
    me = await client.get(f"{API}/auth/me", headers=headers)
    assert me.json()["roles"] == ["farmer"]


async def test_role_guard_blocks_wrong_role(client):
    """Faqat dehqon roli bo'lgan foydalanuvchi restoran endpointiga kira olmaydi."""
    phone = rand_phone()
    headers = await auth_headers(client, phone, role="farmer")
    r = await client.get(f"{API}/orders/mine", headers=headers)
    assert r.status_code == 403
