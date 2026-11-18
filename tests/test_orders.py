import pytest

from conftest import assert_error, make_product, make_order


def stock(client, pid):
    return client.get(f"/products/{pid}").json()["stock"]


def test_create_order_happy_and_stock_decrement(client, customer):
    p1 = make_product(client, "A", 10.50, 10)
    p2 = make_product(client, "B", 0.99, 5)
    r = make_order(client, customer["id"], [
        {"product_id": p1["id"], "quantity": 3}, {"product_id": p2["id"], "quantity": 2}])
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["status"] == "PENDING" and o["customer_id"] == customer["id"]
    assert o["total"] == pytest.approx(3 * 10.50 + 2 * 0.99)
    assert {(i["product_id"], i["quantity"], i["unit_price"]) for i in o["items"]} == {
        (p1["id"], 3, 10.5), (p2["id"], 2, 0.99)}
    assert o["created_at"].endswith("Z") or "+00:00" in o["created_at"]
    assert stock(client, p1["id"]) == 7 and stock(client, p2["id"]) == 3
    assert client.get(f"/orders/{o['id']}").json() == o


def test_total_precision(client, customer):
    p = make_product(client, "C", 0.10, 100)
    o = make_order(client, customer["id"], [{"product_id": p["id"], "quantity": 3}]).json()
    assert o["total"] == 0.3


def test_unit_price_unchanged_after_product_put(client, customer, product):
    o = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 2}]).json()
    client.put(f"/products/{product['id']}", json={"name": "Widget", "price": 99.99, "stock": 50})
    o2 = client.get(f"/orders/{o['id']}").json()
    assert o2["items"][0]["unit_price"] == 10.0 and o2["total"] == 20.0


def test_client_cannot_set_total_or_status(client, customer, product):
    r = client.post("/orders", json={"customer_id": customer["id"], "total": 0.01, "status": "PAID",
                                     "items": [{"product_id": product["id"], "quantity": 1, "unit_price": 0.01}]})
    assert r.status_code == 201
    o = r.json()
    assert o["status"] == "PENDING" and o["total"] == 10.0 and o["items"][0]["unit_price"] == 10.0


def test_insufficient_stock_no_side_effects(client, customer):
    p1 = make_product(client, "A", 1, 5)
    p2 = make_product(client, "B", 1, 1)
    r = make_order(client, customer["id"], [
        {"product_id": p1["id"], "quantity": 2}, {"product_id": p2["id"], "quantity": 2}])
    assert_error(r, 409, "INSUFFICIENT_STOCK")
    assert stock(client, p1["id"]) == 5 and stock(client, p2["id"]) == 1
    assert client.get("/orders").json() == []


def test_order_exact_stock_ok(client, customer):
    p = make_product(client, "A", 1, 4)
    assert make_order(client, customer["id"], [{"product_id": p["id"], "quantity": 4}]).status_code == 201
    assert stock(client, p["id"]) == 0


def test_missing_customer_vs_product(client, customer, product):
    r = make_order(client, 9999, [{"product_id": product["id"], "quantity": 1}])
    assert_error(r, 404, "CUSTOMER_NOT_FOUND")
    r = make_order(client, customer["id"], [{"product_id": 9999, "quantity": 1}])
    assert_error(r, 404, "PRODUCT_NOT_FOUND")
    assert stock(client, product["id"]) == 10


def _bad_bodies(c, p):
    item = {"product_id": p, "quantity": 1}
    return [
        {},
        {"customer_id": c},
        {"items": [item]},
        {"customer_id": c, "items": []},
        {"customer_id": c, "items": "x"},
        {"customer_id": "abc", "items": [item]},
        {"customer_id": c, "items": [{"product_id": p, "quantity": 0}]},
        {"customer_id": c, "items": [{"product_id": p, "quantity": -3}]},
        {"customer_id": c, "items": [{"product_id": p, "quantity": 1.5}]},
        {"customer_id": c, "items": [{"product_id": p}]},
        {"customer_id": c, "items": [{"quantity": 1}]},
        {"customer_id": c, "items": [{"product_id": 0, "quantity": 1}]},
        {"customer_id": 0, "items": [item]},
        {"customer_id": c, "items": [item, {"product_id": p, "quantity": 2}]},
    ]


@pytest.mark.parametrize("idx", range(14))
def test_create_order_validation(client, customer, product, idx):
    body = _bad_bodies(customer["id"], product["id"])[idx]
    assert_error(client.post("/orders", json=body), 422, "VALIDATION_ERROR")
    assert stock(client, product["id"]) == 10


def test_duplicate_product_detail(client, customer, product):
    pid = product["id"]
    e = assert_error(make_order(client, customer["id"], [
        {"product_id": pid, "quantity": 1}, {"product_id": pid, "quantity": 1}]), 422, "VALIDATION_ERROR")
    assert e["details"][0]["field"] == "items"


def test_list_orders_filters_and_pagination(client):
    c1 = client.post("/customers", json={"name": "A", "email": "a@x.com"}).json()
    c2 = client.post("/customers", json={"name": "B", "email": "b@x.com"}).json()
    p = make_product(client, "P", 1, 100)
    ids = []
    for c in (c1, c1, c2, c2, c2):
        ids.append(make_order(client, c["id"], [{"product_id": p["id"], "quantity": 1}]).json()["id"])
    client.patch(f"/orders/{ids[0]}/status", json={"status": "PAID"})
    all_ = client.get("/orders").json()
    assert [o["id"] for o in all_] == sorted(ids)
    assert [o["id"] for o in client.get("/orders?status=PAID").json()] == [ids[0]]
    assert len(client.get("/orders?status=PENDING").json()) == 4
    assert client.get("/orders?status=SHIPPED").json() == []
    assert [o["id"] for o in client.get(f"/orders?customer_id={c1['id']}").json()] == ids[:2]
    assert [o["id"] for o in client.get(f"/orders?customer_id={c2['id']}&status=PENDING").json()] == ids[2:]
    assert client.get("/orders?customer_id=9999").json() == []
    assert [o["id"] for o in client.get("/orders?limit=2").json()] == ids[:2]
    assert [o["id"] for o in client.get("/orders?limit=2&offset=2").json()] == ids[2:4]
    assert client.get("/orders?offset=100").json() == []
    assert client.get("/orders?limit=200").status_code == 200
    assert client.get("/orders?limit=1").status_code == 200


@pytest.mark.parametrize("q", ["limit=0", "limit=201", "limit=-1", "offset=-1", "status=BOGUS",
                               "status=pending", "customer_id=0", "customer_id=abc", "limit=1.5"])
def test_list_orders_bad_query(client, q):
    assert_error(client.get(f"/orders?{q}"), 422, "VALIDATION_ERROR")


def test_get_order_404_422(client):
    assert_error(client.get("/orders/999"), 404, "ORDER_NOT_FOUND")
    assert_error(client.get("/orders/abc"), 422, "VALIDATION_ERROR")
    assert_error(client.get("/orders/0"), 422, "VALIDATION_ERROR")


def _order(client, customer, product, qty=2):
    return make_order(client, customer["id"], [{"product_id": product["id"], "quantity": qty}]).json()


def _set(client, oid, st):
    return client.patch(f"/orders/{oid}/status", json={"status": st})


def test_happy_lifecycle(client, customer, product):
    o = _order(client, customer, product)
    for st in ("PAID", "SHIPPED", "DELIVERED"):
        r = _set(client, o["id"], st)
        assert r.status_code == 200 and r.json()["status"] == st
    assert client.get(f"/orders/{o['id']}").json()["status"] == "DELIVERED"
    assert stock(client, product["id"]) == 8


@pytest.mark.parametrize("start", ["PENDING", "PAID"])
def test_cancel_restores_stock(client, customer, product, start):
    o = _order(client, customer, product, 4)
    assert stock(client, product["id"]) == 6
    if start == "PAID":
        _set(client, o["id"], "PAID")
    r = _set(client, o["id"], "CANCELLED")
    assert r.status_code == 200 and r.json()["status"] == "CANCELLED"
    assert stock(client, product["id"]) == 10
    # cancelling twice must not restore stock twice
    assert_error(_set(client, o["id"], "CANCELLED"), 409, "INVALID_STATUS_TRANSITION")
    assert stock(client, product["id"]) == 10


ALL = ["PENDING", "PAID", "SHIPPED", "DELIVERED", "CANCELLED"]
ALLOWED = {("PENDING", "PAID"), ("PAID", "SHIPPED"), ("SHIPPED", "DELIVERED"),
           ("PENDING", "CANCELLED"), ("PAID", "CANCELLED")}
PATH = {"PENDING": [], "PAID": ["PAID"], "SHIPPED": ["PAID", "SHIPPED"],
        "DELIVERED": ["PAID", "SHIPPED", "DELIVERED"], "CANCELLED": ["CANCELLED"]}


@pytest.mark.parametrize("src", ALL)
@pytest.mark.parametrize("dst", ALL)
def test_transition_matrix(client, customer, product, src, dst):
    o = _order(client, customer, product, 1)
    for st in PATH[src]:
        assert _set(client, o["id"], st).status_code == 200
    r = _set(client, o["id"], dst)
    if (src, dst) in ALLOWED:
        assert r.status_code == 200 and r.json()["status"] == dst
    else:
        assert_error(r, 409, "INVALID_STATUS_TRANSITION")
        assert client.get(f"/orders/{o['id']}").json()["status"] == src


def test_cannot_cancel_delivered_keeps_stock(client, customer, product):
    o = _order(client, customer, product, 3)
    for st in ("PAID", "SHIPPED", "DELIVERED"):
        _set(client, o["id"], st)
    assert_error(_set(client, o["id"], "CANCELLED"), 409, "INVALID_STATUS_TRANSITION")
    assert stock(client, product["id"]) == 7


@pytest.mark.parametrize("body", [{}, {"status": "BOGUS"}, {"status": "paid"}, {"status": 1}, {"status": None}])
def test_status_body_validation(client, customer, product, body):
    o = _order(client, customer, product)
    assert_error(client.patch(f"/orders/{o['id']}/status", json=body), 422, "VALIDATION_ERROR")


def test_patch_unknown_order(client):
    assert_error(_set(client, 999, "PAID"), 404, "ORDER_NOT_FOUND")
    assert_error(client.patch("/orders/abc/status", json={"status": "PAID"}), 422, "VALIDATION_ERROR")
