# Handoff: architect

Read `docs/architecture.md` and `docs/api-contract.yaml` first.

## Decisions
- Layers: API -> Service -> Repository -> DB. Added `app/repositories/` and `app/core/errors.py`.
- Order status stored as enum PENDING, PAID, SHIPPED, DELIVERED, CANCELLED; new orders start PENDING.
- Status change via `PATCH /orders/{id}/status`; transitions enforced in the service.
- Orders embed items; item stores `unit_price` snapshot. Order `total` is server-calculated (may be stored or computed; stored is fine).
- Money: Numeric(10,2) / Decimal, >= 0. Stock integer >= 0. Quantity > 0.
- Customer email unique. Product delete blocked (409 PRODUCT_IN_USE) if referenced by an order item, so FK must not cascade-delete items.
- Same product twice in one order is rejected (422).
- Errors: one format `{"error": {"code", "message", "details?"}}`; codes listed in architecture.md.
- Pagination: `limit`/`offset` on list endpoints; list orders filters `status`, `customer_id`.
- `created_at` UTC, set by the server.

## Next: database agent
1. Write `docs/data-model.md` (tables: customers, products, orders, order_items; columns, types, constraints, FKs, indexes).
2. Implement `app/models` (SQLAlchemy 2.x typed `Mapped`) and `app/db` (engine, SessionLocal, Base, `get_db`, create-tables helper).
3. Add `app/db/seed.py` runnable via `python -m app.db.seed` (a few customers and products).
4. Constraints: UNIQUE customers.email; CHECK price >= 0, stock >= 0, quantity > 0; indexes on orders.customer_id, orders.status, order_items.order_id; enable SQLite `PRAGMA foreign_keys=ON`.
5. Write `docs/handoff-database.md`. Do not write schemas, services, or routers.

## Open questions
- Product PUT is full replace (name, price, stock all required); no PATCH. Change if wanted.
- Order items cannot be edited after creation (not in requirements).
- Unknown product/customer inside an order body returns 404 (not 422).
