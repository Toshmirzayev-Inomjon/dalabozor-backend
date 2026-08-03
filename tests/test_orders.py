"""Restoran (katalog + buyurtma + invoice) va allocation testlari."""
from datetime import date

from tests.conftest import API, auth_headers, rand_phone


async def _products(client, headers):
    r = await client.get(f"{API}/catalog", params={"date": date.today().isoformat()}, headers=headers)
    assert r.status_code == 200, "seed kerak"
    return r.json()


async def test_catalog_and_create_order(client):
    headers = await auth_headers(client, rand_phone(), role="restaurant")
    catalog = await _products(client, headers)
    assert catalog, "katalog bo'sh — seed kerak"
    product = catalog[0]

    r = await client.post(
        f"{API}/orders",
        json={
            "items": [{"product_id": product["product_id"], "kg": 30}],
            "delivery_date": date.today().isoformat(),
            "payment_type": "cash",
        },
        headers=headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["total_sum"] == 30 * product["sell_price"]
    order_id = body["id"]

    # detail + timeline
    d = await client.get(f"{API}/orders/{order_id}", headers=headers)
    assert d.status_code == 200
    assert len(d.json()["timeline"]) == 6

    # invoice PDF
    inv = await client.get(f"{API}/orders/{order_id}/invoice", headers=headers)
    assert inv.status_code == 200
    assert inv.content[:4] == b"%PDF"


async def test_reorder(client):
    headers = await auth_headers(client, rand_phone(), role="restaurant")
    catalog = await _products(client, headers)
    product = catalog[0]
    r = await client.post(
        f"{API}/orders",
        json={
            "items": [{"product_id": product["product_id"], "kg": 25}],
            "delivery_date": date.today().isoformat(),
            "payment_type": "cash",
        },
        headers=headers,
    )
    order_id = r.json()["id"]
    re = await client.post(
        f"{API}/orders/{order_id}/reorder",
        params={"delivery_date": date.today().isoformat()},
        headers=headers,
    )
    assert re.status_code == 201
    assert re.json()["items"][0]["kg"] == 25


async def test_allocation_creates_route(client):
    """Dehqon e'lon → restoran buyurtma → admin allocation → marshrut yaratiladi."""
    today = date.today().isoformat()
    farmer = await auth_headers(client, rand_phone(), role="farmer")
    prices = (await client.get(f"{API}/prices/today", headers=farmer)).json()
    product_id = prices[0]["product_id"]

    await client.post(
        f"{API}/offers",
        json={"product_id": product_id, "date": today, "kg": 200,
              "price_per_kg": prices[0]["buy_price"], "source": "app"},
        headers=farmer,
    )
    restaurant = await auth_headers(client, rand_phone(), role="restaurant")
    await client.post(
        f"{API}/orders",
        json={"items": [{"product_id": product_id, "kg": 40}],
              "delivery_date": today, "payment_type": "cash"},
        headers=restaurant,
    )
    admin = await auth_headers(client, rand_phone(), role="admin")
    r = await client.post(f"{API}/admin/allocation/run", params={"target": today}, headers=admin)
    assert r.status_code == 200
    assert r.json()["detail"]["allocated_kg"] >= 40
    assert r.json()["detail"]["stops"] >= 1
