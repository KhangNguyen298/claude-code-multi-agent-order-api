# Architecture

Stack: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, SQLite, pytest.
The contract in `docs/api-contract.yaml` is the source of truth for the HTTP surface.

## Folder structure

```
app/
  main.py            # FastAPI app, router registration, exception handlers
  api/               # Routers only: parse request, call service, return response
    products.py
    customers.py
    orders.py
    deps.py          # get_db session dependency, service providers
  services/          # Business logic, transactions, domain exceptions use
    product_service.py
    customer_service.py
    order_service.py
  repositories/      # All SQLAlchemy queries (one per aggregate)
    product_repo.py
    customer_repo.py
    order_repo.py
  models/            # SQLAlchemy ORM models
  schemas/           # Pydantic v2 request/response models
  db/                # engine, SessionLocal, Base, seed.py
  core/
    errors.py        # AppError hierarchy + error codes
tests/
docs/
```

Note: a `app/repositories/` folder is added to the requested layout because the
layering rule requires a Repository layer.

## Layering rules

API -> Service -> Repository -> DB. Calls only go downward.

- API (routers): HTTP concerns only. Validate via schemas, call one service method,
  map result to a response schema and status code. No business logic, no SQLAlchemy
  queries, no status-transition checks.
- Service: all business rules (stock checks, total calculation, status transitions,
  uniqueness checks, stock return on cancel). Owns the transaction (commit/rollback).
  Raises `AppError` subclasses. Knows nothing about HTTP or FastAPI.
- Repository: data access only (get, list, add, delete, filters). No business rules,
  no commit. Takes a `Session`.
- DB/models: ORM models and session setup. No logic.
- Schemas never import models; services return ORM objects, routers serialize them
  (`from_attributes=True`).

## Business rules (enforced in services)

- Order creation is one transaction: validate all items, check stock for every item,
  decrement stock, store `unit_price` snapshot per item, compute
  `total = sum(unit_price * quantity)`. Any failure rolls back everything.
- Same product repeated in one order's items is rejected (422 `VALIDATION_ERROR`) to
  keep stock checks simple.
- Status transitions: PENDING->PAID, PAID->SHIPPED, SHIPPED->DELIVERED,
  PENDING->CANCELLED, PAID->CANCELLED. Anything else (including same->same) is
  409 `INVALID_STATUS_TRANSITION`. Cancelling returns each item's quantity to stock.
- Deleting a product referenced by any order item is 409 `PRODUCT_IN_USE`.
- Customer email is unique: duplicate is 409 `EMAIL_ALREADY_EXISTS`.
- Money: non-negative decimal with 2 places; stored as Decimal/Numeric, serialized as
  JSON number in the contract.

## Error handling

One format for every error, including validation and unknown routes:

```json
{"error": {"code": "PRODUCT_NOT_FOUND", "message": "Product 7 not found"}}
```

Validation errors may add optional `details` (list of `{field, message}`).

| HTTP | code | When |
|------|------|------|
| 400 | BAD_REQUEST | Malformed request not covered below |
| 404 | PRODUCT_NOT_FOUND / CUSTOMER_NOT_FOUND / ORDER_NOT_FOUND | Resource id missing (also for a missing product or customer referenced inside an order body) |
| 409 | EMAIL_ALREADY_EXISTS | Duplicate customer email |
| 409 | INSUFFICIENT_STOCK | Item quantity exceeds stock |
| 409 | INVALID_STATUS_TRANSITION | Transition not allowed |
| 409 | PRODUCT_IN_USE | Delete product used by orders |
| 422 | VALIDATION_ERROR | Pydantic/query validation failure (quantity <= 0, bad enum, empty items, ...) |
| 500 | INTERNAL_ERROR | Unexpected; message is generic, no stack trace |

Implementation: `app/core/errors.py` defines `AppError(status_code, code, message)`.
`main.py` registers handlers for `AppError`, `RequestValidationError` (-> 422),
`StarletteHTTPException` (e.g. 404 route, 405) and a catch-all `Exception` (-> 500), all
producing the standard format.

## Conventions

- IDs are integers. Timestamps are UTC ISO 8601 (`created_at`).
- List endpoints use `limit` (default 50, 1-200) and `offset` (default 0) and return a
  plain JSON array.
- Create returns 201; delete returns 204; others 200.
- Tests use a separate SQLite DB (in-memory) through a `get_db` dependency override.
