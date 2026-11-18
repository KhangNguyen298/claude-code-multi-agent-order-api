# Handoff: database

Read `docs/data-model.md` for tables, constraints and the ER diagram.

## Files
- `app/db/session.py`: `engine`, `SessionLocal`, `Base`, `get_db()`, `init_db(bind=None)`. URL from env `DATABASE_URL` (default `sqlite:///./orders.db`). SQLite FK pragma is enabled for every SQLite engine (listener on `Engine`, so test engines get it too).
- `app/models/`: `Customer`, `Product`, `Order`, `OrderItem`, `OrderStatus` (str Enum), `types.Money`. Import from `app.models`.
- `app/db/seed.py`: `python -m app.db.seed` creates tables and inserts 2 customers, 4 products (one with stock 0), 3 orders. Idempotent (skips if customers exist). Verified: runs cleanly, FK RESTRICT and CHECK constraints fire.

## Relationships
- `Customer.orders` <-> `Order.customer`
- `Order.items` (ordered by id, `cascade="all, delete-orphan"`) <-> `OrderItem.order`
- `OrderItem.product` (one-way)

## Things the backend must know
- Money attributes (`Product.price`, `OrderItem.unit_price`, `Order.total`) are `Decimal` with 2 places. DB stores integer cents. Never pass floats; pass `Decimal` (or str). Pydantic schemas should use `Decimal` and serialize to JSON number.
- Order total: stored column, NOT auto-computed. In the service: `order.total = sum(i.unit_price * i.quantity for i in order.items)` with `unit_price` copied from `product.price` at creation.
- Models contain no logic and no commit. Services own transactions (`db.commit()`/`rollback()`). Session uses `autoflush=False` and `expire_on_commit=False`; call `db.flush()` to get ids.
- Stock: DB CHECK stock >= 0 is a safety net only. Check stock in the service first to raise `INSUFFICIENT_STOCK`; decrement on create, increment on cancel.
- Duplicate email: catch `IntegrityError` on flush or pre-check (`EMAIL_ALREADY_EXISTS`). Same product twice in an order: reject in schema/service (422) before DB UNIQUE (order_id, product_id) fires.
- Product delete: catch `sqlalchemy.exc.IntegrityError` on commit (rollback first) -> 409 `PRODUCT_IN_USE`; or pre-check via `order_items.product_id`.
- `Order.status` is `OrderStatus`; the str-Enum compares equal to strings and serializes as `"PENDING"` etc. Invalid values are rejected by a DB CHECK.
- `created_at` is UTC but stored/returned as a naive datetime (SQLite drops tzinfo). Serialize as UTC (e.g. attach `tzinfo=timezone.utc` or append `Z`) so the contract's date-time is correct.
- Tests: create an in-memory engine with `create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)`, call `init_db(bind=engine)`, and override `get_db`.
- `orders.db` is created in the CWD by the seed run; delete it to reset.

## Next: backend agent
Write `app/schemas`, `app/repositories`, `app/services`, `app/api`, `app/core/errors.py`, `app/main.py` per `docs/architecture.md`; call `init_db()` at app startup (lifespan) so tables exist.
