import pytest
from sqlalchemy.exc import IntegrityError

from conftest import assert_error, make_product, make_order

BIG = 2 ** 63


def _products(client, n, stock=5, price=1.00):
    return [make_product(client, f"P{i}", price, stock) for i in range(n)]


def test_101_items_rejected(client, customer):
    ps = _products(client, 101)
    items = [{"product_id": p["id"], "quantity": 1} for p in ps]
    err = assert_error(make_order(client, customer["id"], items), 422, "VALIDATION_ERROR")
    assert err["details"][0]["field"] == "items"
    # nothing was decremented
    assert client.get(f"/products/{ps[0]['id']}").json()["stock"] == 5


def test_100_items_ok(client, customer):
    ps = _products(client, 100, price=1.50)
    items = [{"product_id": p["id"], "quantity": 2} for p in ps]
    r = make_order(client, customer["id"], items)
    assert r.status_code == 201, r.text
    assert len(r.json()["items"]) == 100
    assert r.json()["total"] == 300.0
    assert client.get(f"/products/{ps[99]['id']}").json()["stock"] == 3


def test_total_over_limit_422(client, customer):
    p = make_product(client, "Gold", 9999999999.99, 10)
    r = make_order(client, customer["id"], [{"product_id": p["id"], "quantity": 2}])
    assert_error(r, 422, "VALIDATION_ERROR")
    # rolled back: stock untouched, no order created
    assert client.get(f"/products/{p['id']}").json()["stock"] == 10
    assert client.get("/orders").json() == []


def test_total_exactly_at_limit_ok(client, customer):
    p = make_product(client, "Gold", 9999999999.99, 10)
    r = make_order(client, customer["id"], [{"product_id": p["id"], "quantity": 1}])
    assert r.status_code == 201, r.text
    assert r.json()["total"] == 9999999999.99


def test_total_over_limit_across_items_422(client, customer):
    a = make_product(client, "A", 9999999999.99, 1)
    b = make_product(client, "B", 0.01, 1)
    r = make_order(client, customer["id"], [
        {"product_id": a["id"], "quantity": 1}, {"product_id": b["id"], "quantity": 1}])
    assert_error(r, 422, "VALIDATION_ERROR")
    assert client.get(f"/products/{b['id']}").json()["stock"] == 1


def test_original_overflow_case_now_422(client, customer):
    p = make_product(client, "Gold", 9999999999.99, 10 ** 9)
    r = make_order(client, customer["id"], [{"product_id": p["id"], "quantity": 10 ** 9}])
    assert_error(r, 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("path", [
    f"/products/{BIG}", f"/customers/{BIG}", f"/orders/{BIG}", f"/orders/{10**30}",
])
def test_path_ids_out_of_range(client, path):
    assert_error(client.get(path), 422, "VALIDATION_ERROR")


def test_path_id_boundary_is_404(client):
    m = 2 ** 63 - 1
    for p in (f"/products/{m}", f"/customers/{m}", f"/orders/{m}"):
        assert client.get(p).status_code == 404


def test_put_delete_patch_out_of_range_ids(client):
    body = {"name": "x", "price": 1, "stock": 1}
    assert_error(client.put(f"/products/{BIG}", json=body), 422, "VALIDATION_ERROR")
    assert_error(client.delete(f"/products/{BIG}"), 422, "VALIDATION_ERROR")
    assert_error(client.patch(f"/orders/{BIG}/status", json={"status": "PAID"}), 422, "VALIDATION_ERROR")


def test_stock_out_of_range(client, product):
    for v in (BIG, 10 ** 30):
        assert_error(client.post("/products", json={"name": "x", "price": 1, "stock": v}), 422, "VALIDATION_ERROR")
        assert_error(client.put(f"/products/{product['id']}", json={"name": "x", "price": 1, "stock": v}), 422, "VALIDATION_ERROR")
    r = client.post("/products", json={"name": "x", "price": 1, "stock": 2 ** 63 - 1})
    assert r.status_code == 201, r.text


def test_order_ids_out_of_range(client, customer, product):
    assert_error(make_order(client, BIG, [{"product_id": product["id"], "quantity": 1}]), 422, "VALIDATION_ERROR")
    assert_error(make_order(client, customer["id"], [{"product_id": BIG, "quantity": 1}]), 422, "VALIDATION_ERROR")


def test_quantity_huge_is_409_not_500(client, customer, product):
    for q in (BIG, 10 ** 30):
        assert_error(make_order(client, customer["id"], [{"product_id": product["id"], "quantity": q}]), 409, "INSUFFICIENT_STOCK")


def test_query_params_out_of_range(client):
    assert_error(client.get(f"/orders?customer_id={BIG}"), 422, "VALIDATION_ERROR")
    assert_error(client.get(f"/orders?offset={BIG}"), 422, "VALIDATION_ERROR")
    assert_error(client.get(f"/products?offset={BIG}"), 422, "VALIDATION_ERROR")
    assert client.get(f"/orders?offset={2**63-1}").status_code == 200


# ---- regression checks on the IntegrityError -> 409 mapping ----

def test_integrity_error_in_create_order_maps_to_409(client, customer, product, monkeypatch):
    from app.repositories import order_repo
    orig = order_repo.add

    def boom(db, order):
        raise IntegrityError("stmt", {}, Exception("CHECK constraint failed: ck_products_stock_nonneg"))
    monkeypatch.setattr(order_repo, "add", boom)
    r = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 1}])
    err = assert_error(r, 409, "INSUFFICIENT_STOCK")
    assert err["message"] == "Insufficient stock for one or more products"
    monkeypatch.setattr(order_repo, "add", orig)
    assert client.get(f"/products/{product['id']}").json()["stock"] == 10


def test_non_integrity_errors_still_500_clean(client, customer, product, monkeypatch):
    from app.repositories import order_repo

    def boom(db, order):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(order_repo, "add", boom)
    r = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 1}])
    err = assert_error(r, 500, "INTERNAL_ERROR")
    assert "secret" not in r.text
    assert client.get(f"/products/{product['id']}").json()["stock"] == 10


def test_fk_violation_now_500_internal_error(client, customer, product, monkeypatch):
    """BUG-3 fix: non-stock IntegrityError is no longer masked as INSUFFICIENT_STOCK."""
    from app.repositories import order_repo

    def boom(db, order):
        raise IntegrityError("stmt", {}, Exception("FOREIGN KEY constraint failed"))
    monkeypatch.setattr(order_repo, "add", boom)
    r = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 1}])
    assert_error(r, 500, "INTERNAL_ERROR")
    assert "FOREIGN" not in r.text and "stock" not in r.text.lower()
    monkeypatch.undo()
    assert client.get(f"/products/{product['id']}").json()["stock"] == 10


def test_non_stock_check_failure_not_reported_as_stock(client, customer, product, monkeypatch):
    from app.repositories import order_repo

    def boom(db, order):
        raise IntegrityError("stmt", {}, Exception("CHECK constraint failed: ck_order_items_quantity_positive"))
    monkeypatch.setattr(order_repo, "add", boom)
    r = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 1}])
    assert_error(r, 500, "INTERNAL_ERROR")
    assert "INSUFFICIENT_STOCK" not in r.text
    assert "ck_order_items" not in r.text
    monkeypatch.undo()
    assert client.get(f"/products/{product['id']}").json()["stock"] == 10


def test_generic_stock_check_text_variant_maps_to_409(client, customer, product, monkeypatch):
    from app.repositories import order_repo

    def boom(db, order):
        raise IntegrityError("stmt", {}, Exception("CHECK constraint failed: stock >= 0"))
    monkeypatch.setattr(order_repo, "add", boom)
    r = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 1}])
    assert_error(r, 409, "INSUFFICIENT_STOCK")


def test_regressions_core_flow_still_ok(client, customer, product):
    r = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 3}])
    assert r.status_code == 201 and r.json()["total"] == 30.0
    oid = r.json()["id"]
    assert client.patch(f"/orders/{oid}/status", json={"status": "CANCELLED"}).status_code == 200
    assert client.get(f"/products/{product['id']}").json()["stock"] == 10
    assert_error(client.patch(f"/orders/{oid}/status", json={"status": "PAID"}), 409, "INVALID_STATUS_TRANSITION")
