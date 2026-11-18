import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import get_db, init_db
from app.main import app


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(bind=eng)
    return eng


@pytest.fixture(scope="session")
def TestSession(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def clean_db(engine):
    yield
    with engine.begin() as c:
        for t in ("order_items", "orders", "products", "customers"):
            c.execute(text(f"DELETE FROM {t}"))


@pytest.fixture
def client(TestSession):
    def _get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    # no lifespan (no `with`) so the real orders.db is never touched
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def customer(client):
    r = client.post("/customers", json={"name": "Ann", "email": "ann@example.com"})
    assert r.status_code == 201
    return r.json()


def make_product(client, name="Widget", price=10.00, stock=10):
    r = client.post("/products", json={"name": name, "price": price, "stock": stock})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def product(client):
    return make_product(client)


def make_order(client, customer_id, items):
    return client.post("/orders", json={"customer_id": customer_id, "items": items})


def assert_error(r, status, code=None):
    assert r.status_code == status, r.text
    body = r.json()
    assert set(body.keys()) == {"error"}
    assert "code" in body["error"] and "message" in body["error"]
    if code:
        assert body["error"]["code"] == code
    low = r.text.lower()
    assert "traceback" not in low and "sqlalchemy" not in low and 'file "' not in low
    return body["error"]
