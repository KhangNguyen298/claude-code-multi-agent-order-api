import pytest

from conftest import assert_error, make_product, make_order


def test_product_crud(client):
    p = make_product(client, "Pen", 1.5, 3)
    assert p["name"] == "Pen" and p["price"] == 1.5 and p["stock"] == 3
    assert client.get(f"/products/{p['id']}").json() == p
    assert client.get("/products").json() == [p]
    r = client.put(f"/products/{p['id']}", json={"name": "Pen2", "price": 2, "stock": 9})
    assert r.status_code == 200 and r.json()["name"] == "Pen2" and r.json()["stock"] == 9
    d = client.delete(f"/products/{p['id']}")
    assert d.status_code == 204 and d.content == b""
    assert_error(client.get(f"/products/{p['id']}"), 404, "PRODUCT_NOT_FOUND")


def test_product_pagination(client):
    for i in range(5):
        make_product(client, f"P{i}")
    assert len(client.get("/products?limit=2").json()) == 2
    assert len(client.get("/products?limit=2&offset=4").json()) == 1
    for q in ("limit=0", "limit=201", "offset=-1", "limit=abc"):
        assert_error(client.get(f"/products?{q}"), 422, "VALIDATION_ERROR")
    assert client.get("/products?limit=200").status_code == 200


@pytest.mark.parametrize("body", [
    {}, {"name": "x"}, {"name": "x", "price": 1}, {"price": 1, "stock": 1},
    {"name": "", "price": 1, "stock": 1},
    {"name": "x", "price": "abc", "stock": 1},
    {"name": "x", "price": -1, "stock": 1},
    {"name": "x", "price": 1, "stock": -1},
    {"name": "x", "price": 1, "stock": "many"},
    {"name": "x", "price": 1, "stock": 1.5},
    {"name": "x" * 201, "price": 1, "stock": 1},
    {"name": 123, "price": 1, "stock": 1},
    {"name": "x", "price": 1.001, "stock": 1},
])
def test_product_validation(client, body):
    assert_error(client.post("/products", json=body), 422, "VALIDATION_ERROR")


def test_product_put_validation_and_404(client):
    assert_error(client.put("/products/999", json={"name": "a", "price": 1, "stock": 1}), 404, "PRODUCT_NOT_FOUND")
    p = make_product(client)
    assert_error(client.put(f"/products/{p['id']}", json={"name": "a"}), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("method", ["get", "delete"])
def test_product_missing_and_bad_id(client, method):
    assert_error(getattr(client, method)("/products/999"), 404, "PRODUCT_NOT_FOUND")
    assert_error(getattr(client, method)("/products/abc"), 422, "VALIDATION_ERROR")
    assert_error(getattr(client, method)("/products/0"), 422, "VALIDATION_ERROR")


def test_validation_field_has_no_prefix(client):
    e = assert_error(client.post("/products", json={"name": "x", "price": 1}), 422, "VALIDATION_ERROR")
    assert e["details"][0]["field"] == "stock"
    e = assert_error(client.get("/products?limit=0"), 422)
    assert e["details"][0]["field"] == "limit"
    for d in e["details"]:
        assert not d["field"].startswith(("body", "query", "path"))
    e = assert_error(client.post("/orders", json={"customer_id": 1, "items": [{"product_id": 1, "quantity": 0}]}), 422)
    assert e["details"][0]["field"] == "items.0.quantity"


def test_product_delete_in_use(client, customer, product):
    assert make_order(client, customer["id"], [{"product_id": product["id"], "quantity": 1}]).status_code == 201
    assert_error(client.delete(f"/products/{product['id']}"), 409, "PRODUCT_IN_USE")
    assert client.get(f"/products/{product['id']}").status_code == 200


def test_customer_create_get(client):
    r = client.post("/customers", json={"name": "Bob", "email": "bob@example.com"})
    assert r.status_code == 201
    c = r.json()
    assert c["name"] == "Bob" and c["email"] == "bob@example.com" and c["id"]
    assert client.get(f"/customers/{c['id']}").json() == c


def test_customer_duplicate_email(client, customer):
    r = client.post("/customers", json={"name": "Other", "email": customer["email"]})
    assert_error(r, 409, "EMAIL_ALREADY_EXISTS")


def test_customer_404_and_bad_id(client):
    assert_error(client.get("/customers/999"), 404, "CUSTOMER_NOT_FOUND")
    assert_error(client.get("/customers/abc"), 422, "VALIDATION_ERROR")
    assert_error(client.get("/customers/0"), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("body", [
    {}, {"name": "A"}, {"email": "a@b.co"},
    {"name": "", "email": "a@b.co"},
    {"name": "A", "email": "not-an-email"},
    {"name": "A", "email": "a@b"},
    {"name": "A", "email": 5},
    {"name": 5, "email": "a@b.co"},
    {"name": "A", "email": "a" * 250 + "@b.co"},
    {"name": "A" * 201, "email": "a@b.co"},
    {"name": "A", "email": "a b@c.co"},
])
def test_customer_validation(client, body):
    assert_error(client.post("/customers", json=body), 422, "VALIDATION_ERROR")


def test_malformed_json(client):
    r = client.post("/products", content=b"{not json", headers={"content-type": "application/json"})
    assert_error(r, 422, "VALIDATION_ERROR")
    r = client.post("/products", content=b"[]", headers={"content-type": "application/json"})
    assert_error(r, 422, "VALIDATION_ERROR")
