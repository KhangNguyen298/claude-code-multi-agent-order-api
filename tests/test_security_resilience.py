import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from conftest import assert_error, make_product, make_order

SQLI = ["' OR '1'='1", "'; DROP TABLE products; --", "Robert'); DROP TABLE customers;--", "\" OR 1=1 --", "1; SELECT 1"]


@pytest.mark.parametrize("s", SQLI)
def test_sqli_strings_stored_literally(client, s):
    p = client.post("/products", json={"name": s, "price": 1, "stock": 1})
    assert p.status_code == 201 and p.json()["name"] == s
    assert client.get(f"/products/{p.json()['id']}").json()["name"] == s
    c = client.post("/customers", json={"name": s, "email": "q@x.com"})
    assert c.status_code == 201 and c.json()["name"] == s
    assert client.get("/products").status_code == 200  # tables still alive
    assert client.get("/customers/%d" % c.json()["id"]).status_code == 200


@pytest.mark.parametrize("s", SQLI)
def test_sqli_in_email_rejected_or_safe(client, s):
    r = client.post("/customers", json={"name": "x", "email": s})
    assert r.status_code in (201, 422)
    assert client.get("/products").status_code == 200


@pytest.mark.parametrize("s", SQLI)
def test_sqli_in_query_and_path(client, s):
    for url in (f"/orders?status={s}", f"/orders?customer_id={s}", f"/products?limit={s}"):
        assert_error(client.get(url), 422, "VALIDATION_ERROR")
    for url in (f"/products/{s}", f"/orders/{s}", f"/customers/{s}"):
        r = client.get(url)
        assert r.status_code in (404, 422) and "error" in r.json()


def test_sqli_in_status_body(client, customer, product):
    o = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 1}]).json()
    assert_error(client.patch(f"/orders/{o['id']}/status", json={"status": "PAID'; DROP TABLE orders;--"}), 422)
    assert client.get(f"/orders/{o['id']}").status_code == 200


def test_oversized_payloads(client):
    big = "A" * 2_000_000
    r = client.post("/products", json={"name": big, "price": 1, "stock": 1})
    assert_error(r, 422, "VALIDATION_ERROR")
    r = client.post("/customers", json={"name": "x", "email": big + "@x.com"})
    assert_error(r, 422, "VALIDATION_ERROR")
    r = client.post("/products", json={"name": "x", "price": 1, "stock": 10 ** 30})
    assert r.status_code in (201, 422), r.text  # must not be 500
    r = client.post("/products", json={"name": "x", "price": 10 ** 30, "stock": 1})
    assert_error(r, 422, "VALIDATION_ERROR")


def test_huge_ints_no_500(client, customer, product):
    r = make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 10 ** 30}])
    assert r.status_code in (409, 422), r.text
    r = make_order(client, 10 ** 30, [{"product_id": product["id"], "quantity": 1}])
    assert r.status_code in (404, 422), r.text
    assert client.get(f"/products/{10 ** 30}").status_code in (404, 422)
    assert client.get(f"/orders?customer_id={10 ** 30}").status_code in (200, 422)


def test_huge_item_list(client, customer, product):
    items = [{"product_id": product["id"] + i, "quantity": 1} for i in range(5000)]
    r = make_order(client, customer["id"], items)
    assert r.status_code in (404, 413, 422), r.text


def test_extreme_prices_in_order_no_500(client, customer):
    p = make_product(client, "Gold", 9999999999.99, 10 ** 9)
    r = make_order(client, customer["id"], [{"product_id": p["id"], "quantity": 10 ** 9}])
    assert r.status_code != 500, r.text


def test_unknown_route_and_405_uniform(client):
    e = assert_error(client.get("/nope"), 404)
    assert e["code"] == "BAD_REQUEST"
    assert_error(client.delete("/orders/1"), 405)
    assert_error(client.put("/orders"), 405)
    assert_error(client.post("/customers/1"), 405)
    assert_error(client.patch("/products"), 405)


def test_unhandled_exception_uniform_500():
    def boom():
        raise RuntimeError("secret internal /path/to/file.py SELECT * FROM users")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = boom
    try:
        c = TestClient(app, raise_server_exceptions=False)
        r = c.get("/products")
    finally:
        app.dependency_overrides.clear()
    assert_error(r, 500, "INTERNAL_ERROR")
    assert "secret" not in r.text and "RuntimeError" not in r.text and "SELECT" not in r.text


def test_wrong_content_type_and_empty_body(client):
    r = client.post("/products", content=b"name=x", headers={"content-type": "text/plain"})
    assert_error(r, 422, "VALIDATION_ERROR")
    assert_error(client.post("/orders"), 422, "VALIDATION_ERROR")


def test_422_does_not_echo_internals(client):
    r = client.post("/products", json={"name": "x", "price": "abc", "stock": 1})
    assert r.status_code == 422
    low = r.text.lower()
    assert "pydantic" not in low and "/app/" not in low and "\\\\app\\\\" not in low


def test_email_case_sensitivity_documented(client):
    client.post("/customers", json={"name": "A", "email": "Case@Example.com"})
    r = client.post("/customers", json={"name": "B", "email": "case@example.com"})
    # documented limitation: exact-match comparison, so this is accepted
    assert r.status_code in (201, 409)
