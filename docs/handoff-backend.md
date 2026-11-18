# Handoff: backend

## Files
- `app/core/errors.py`: `AppError(status_code, code, message)` + subclasses (ProductNotFound, CustomerNotFound, OrderNotFound, EmailAlreadyExists, InsufficientStock, InvalidStatusTransition, ProductInUse).
- `app/schemas/`: `common.py` (MoneyOut, as_utc), `product.py`, `customer.py`, `order.py`.
- `app/repositories/`: `product_repo.py`, `customer_repo.py`, `order_repo.py` (queries only, flush but never commit).
- `app/services/`: `product_service.py`, `customer_service.py`, `order_service.py` (own commit/rollback).
- `app/api/`: `products.py`, `customers.py`, `orders.py`, `deps.py` (re-exports `get_db`; override it in tests).
- `app/main.py`: app, routers, handlers, lifespan calling `init_db()`.

## Endpoints (all per contract)
- POST/GET `/products`, GET/PUT/DELETE `/products/{id}`
- POST `/customers`, GET `/customers/{id}`
- POST/GET `/orders` (filters `status`, `customer_id`, `limit`, `offset`, ordered by id), GET `/orders/{id}`, PATCH `/orders/{id}/status`

## Behaviour notes
- Money is `Decimal` internally; serialized as JSON number (float) only at output.
- Order create: customer check (404), all products exist (404), stock check for all items (409 INSUFFICIENT_STOCK), then decrement stock, snapshot unit_price, total = sum(unit_price*qty), single commit; rollback on any failure.
- Duplicate product ids in items: 422 VALIDATION_ERROR (schema validator, field `items`).
- Cancel (PENDING/PAID -> CANCELLED) returns stock. Same->same and all other transitions: 409.
- Product delete: pre-check on order_items plus IntegrityError fallback -> 409 PRODUCT_IN_USE.
- Duplicate email: pre-check plus IntegrityError fallback -> 409. Comparison is exact (case-sensitive).
- `created_at` serialized with UTC tz (`...Z`).
- Error format everywhere: `{"error": {"code","message","details?"}}`. Validation `details[].field` omits the `body`/`query`/`path` prefix (e.g. `items.0.quantity`).

## Run
`uvicorn app.main:app --reload` (tables are created at startup). Smoke-tested via TestClient with an in-memory DB: create/duplicate/validation/stock/in-use/cancel/transition all behave.

## Known limitations / contract issues
- Contract error-code enum has no code for unknown routes (404) or 405; these return the correct HTTP status with code `BAD_REQUEST`. Consider adding `NOT_FOUND` to the enum.
- Email format is checked by a simple regex (`email-validator` is not installed, so `EmailStr` was avoided). Add `email-validator` to requirements if stricter validation is wanted.
- Price accepts up to 12 digits, 2 decimals (contract says multipleOf 0.01 only).
- No concurrency locking on stock (SQLite CHECK stock >= 0 is the safety net; it would surface as 500).
- Starlette emits a deprecation warning about `httpx` for TestClient; harmless.
- No model changes needed.

## QA should check
Stock decrement/restore, total with several items, price snapshot after product PUT, filters and pagination limits (limit 0/201 -> 422), invalid enum for status filter/body (422), PATCH with unknown order (404), 204 delete with empty body, missing customer vs missing product 404 codes.

## QA round 1 fixes
- BUG-1 FIXED: upper bound `le=2**63-1` on product `stock`, order `customer_id`/`product_id`, all path ids, `customer_id` and `offset` query params. Out-of-range values now return 422 VALIDATION_ERROR. Quantity is intentionally unbounded and gives 409 INSUFFICIENT_STOCK (stock is bounded).
- BUG-2 FIXED: order total is checked against 9999999999.99 (Money column limit) before saving; exceeding it returns 422 VALIDATION_ERROR.
- Hardening: `items` max_length=100 (larger lists -> 422). IntegrityError while creating an order (stock CHECK race) is mapped to 409 INSUFFICIENT_STOCK (message uses generic product 0 / 0 available).
- `pytest -q`: 128 passed.
- Contract note: the 100-item cap and 2**63-1 bounds are not in the contract; consider documenting them.

## QA round 2 fixes

- BUG-3 (fixed): `create_order` in `app/services/order_service.py` no longer maps every `IntegrityError` to 409 `INSUFFICIENT_STOCK` (product 0 / 0 available). Only the stock CHECK failure (`ck_products_stock_nonneg` / `stock >= 0`) returns 409 `INSUFFICIENT_STOCK` with a generic message (the offending product id is not reliably available from the DB error). Any other `IntegrityError` (e.g. foreign key) is rolled back and re-raised, producing a 500 `INTERNAL_ERROR`.
