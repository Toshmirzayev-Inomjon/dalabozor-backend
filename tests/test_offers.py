"""Offer + narx koridori testlari."""
from datetime import date

from tests.conftest import API, auth_headers, rand_phone


async def _first_product(client, headers) -> dict:
    r = await client.get(f"{API}/prices/today", headers=headers)
    assert r.status_code == 200, "seed ishga tushirilganmi? (python -m app.seed)"
    prices = r.json()
    assert prices, "Mahsulot narxlari yo'q — seed kerak"
    return prices[0]


async def test_offer_within_corridor_auto_approved(client):
    headers = await auth_headers(client, rand_phone(), role="farmer")
    product = await _first_product(client, headers)
    # yangi dehqon → kechagi ma'lumot yo'q → cheksiz koridor → auto_approved
    r = await client.post(
        f"{API}/offers",
        json={
            "product_id": product["product_id"],
            "date": date.today().isoformat(),
            "kg": 100,
            "price_per_kg": product["buy_price"],
            "source": "app",
        },
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "auto_approved"
    assert r.json()["estimated_income"] == 100 * product["buy_price"]


async def test_offer_out_of_corridor_needs_review(client):
    """Admin koridor o'rnatgach, undan tashqaridagi narx needs_review bo'ladi."""
    admin = await auth_headers(client, rand_phone(), role="admin")
    farmer = await auth_headers(client, rand_phone(), role="farmer")
    product = await _first_product(client, farmer)

    # tor koridor: 4000..4600
    await client.post(
        f"{API}/admin/corridor/{product['product_id']}",
        json={"date": date.today().isoformat(), "min_price": 4000, "max_price": 4600},
        headers=admin,
    )
    r = await client.post(
        f"{API}/offers",
        json={
            "product_id": product["product_id"],
            "date": date.today().isoformat(),
            "kg": 50,
            "price_per_kg": 9999,  # koridordan tashqari
            "source": "app",
        },
        headers=farmer,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "needs_review"


async def test_offers_mine_and_balance(client):
    headers = await auth_headers(client, rand_phone(), role="farmer")
    product = await _first_product(client, headers)
    await client.post(
        f"{API}/offers",
        json={
            "product_id": product["product_id"],
            "date": date.today().isoformat(),
            "kg": 70,
            "price_per_kg": product["buy_price"],
            "source": "app",
        },
        headers=headers,
    )
    mine = await client.get(f"{API}/offers/mine", headers=headers)
    assert mine.status_code == 200
    assert len(mine.json()) >= 1

    bal = await client.get(f"{API}/farmers/me/balance", headers=headers)
    assert bal.status_code == 200
    assert bal.json()["month_kg"] >= 70
