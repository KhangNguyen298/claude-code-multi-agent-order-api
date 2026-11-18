# QA report

Run: `pytest -q` (venv Python, in-memory SQLite, StaticPool, `init_db(bind=engine)`, `get_db` overridden).
Result: **125 passed, 3 failed** (128 tests). Only warning: Starlette `httpx` deprecation (harmless).

Test files (`tests/`): `conftest.py`, `test_products_customers.py`, `test_orders.py`, `test_security_resilience.py`.
Per-test table cleanup on a session-scoped in-memory DB. The app lifespan is not run, so `orders.db` is never touched.

## Coverage summary (all passing unless listed under Bugs)
- Happy path for every endpoint in the contract.
- Stock decrement on create and restore on cancel (PENDING and PAID); double cancel does not restore twice; insufficient stock leaves no side effects (atomic).
- Multi-item totals, 0.10 x 3 = 0.30 precision, unit_price snapshot unchanged after product PUT, client-supplied total/status/unit_price ignored.
- Order list filters (status, customer_id, combined), id ordering, limit/offset; limit 0/201/-1, offset -1, bad status enum (also lowercase), customer_id 0/abc -> 422.
- Invalid status enum in PATCH body (BOGUS, lowercase, int, null, missing) -> 422.
- Missing customer -> 404 CUSTOMER_NOT_FOUND; missing product in body -> 404 PRODUCT_NOT_FOUND.
- DELETE product -> 204 with empty body; 404; PRODUCT_IN_USE 409.
- `details[].field` has no body/query/path prefix (`stock`, `limit`, `items.0.quantity`, `items`).
- Duplicate email 409 EMAIL_ALREADY_EXISTS; duplicate product id in order 422.
- Full 5x5 status transition matrix (25 cases); delivered/cancelled cannot be cancelled again; failed transitions leave status and stock unchanged.
- Uniform `{"error": {...}}` for 404 unknown route (BAD_REQUEST), 405, 422, 404, 409, and 500 (INTERNAL_ERROR, no internals leaked).
- Security: SQL-injection strings in names, emails, query, path, status body (stored literally or rejected, tables intact); 2 MB strings -> 422; no stack traces/SQLAlchemy/path text in any error body.

## Bugs found

### BUG-1 (High): integers beyond SQLite INTEGER range cause 500
`OverflowError: Python int too large to convert to SQLite INTEGER` is raised in the DB layer and surfaces as 500 INTERNAL_ERROR (body is clean, but a 500 is a contract/robustness failure and trivially triggerable by any client). Failing tests: `test_oversized_payloads`, `test_huge_ints_no_500`.

Reproductions (N = 10**30 unless noted), expected vs actual:

| Endpoint | Input | Expected | Actual |
|---|---|---|---|
| POST /products | stock = N | 422 | 500 |
| PUT /products/{id} | stock = N | 422 | 500 |
| GET /products/N, GET /orders/N, GET /customers/N | path id = N | 404 (or 422) | 500 |
| POST /orders | customer_id = N | 404 CUSTOMER_NOT_FOUND or 422 | 500 |
| POST /orders | items[].product_id = N | 404 PRODUCT_NOT_FOUND or 422 | 500 |
| GET /orders?customer_id=N, ?offset=N | query | 200 [] or 422 | 500 |

(POST /orders with quantity = N correctly returns 409 INSUFFICIENT_STOCK.)
Suggested fix: add an upper bound (e.g. `le=2**31-1` or 2**63-1) to all integer fields, path ids and query params in schemas and route signatures.

### BUG-2 (Medium): order total overflow returns 500
Failing test: `test_extreme_prices_in_order_no_500`.
POST /products `{"name":"Gold","price":9999999999.99,"stock":1000000000}` (accepted, valid), then POST /orders with quantity 1000000000 of it. Expected: 422/409 (or a documented total cap). Actual: 500 INTERNAL_ERROR (total in integer cents exceeds the Money column / SQLite range, or Decimal precision error). Suggested fix: cap the total/quantity or catch the overflow and return 422.

## Backend-flagged contract gaps (confirmed, not counted as test failures)
1. No `NOT_FOUND` / `METHOD_NOT_ALLOWED` code in the error enum. Unknown routes (404) and 405 return `BAD_REQUEST` (verified). Recommend adding `NOT_FOUND` and `METHOD_NOT_ALLOWED` to the contract.
2. Email validated by a regex (`^[^@\s]+@[^@\s]+\.[^@\s]+$`), not RFC validation; `email-validator` is not installed. Duplicate check is case-sensitive, so `Case@x.com` and `case@x.com` can both register (test accepts either result, behavior is by design but a risk of duplicate accounts).
3. Price is capped at 12 digits / 2 decimals; the contract only says `multipleOf 0.01`. Prices with 3 decimals are rejected (422), matching the contract; the cap itself should be documented.
4. No concurrency locking on stock. Two simultaneous orders could both pass the service check; the DB `CHECK stock >= 0` would then fail one and surface as 500 instead of 409 INSUFFICIENT_STOCK. Not testable with the single-threaded TestClient; recommended fix is an atomic conditional `UPDATE ... WHERE stock >= :qty` or catching IntegrityError -> 409.

## Security notes
- SQL injection: all DB access is parameterized via SQLAlchemy; injection strings in JSON bodies, query strings and path segments were stored literally or rejected and no table was affected.
- Error responses never contained stack traces, SQL, file paths, or exception class names (including the forced 500 case). Server-side logging of exceptions is in place.
- Oversized input: 2 MB name/email rejected with 422 by length limits. There is no request body size limit at the app level (5000-item order list is processed without 500); consider a reverse-proxy limit and a `max_length` on `items`.
- Integer overflow (BUG-1/BUG-2) is the only remotely triggerable 500 found; it is a reliability/DoS-noise issue, not a data leak.
- No authentication/authorization exists (out of contract scope); any client can read all customers' orders and emails.

## Verdict
2 bugs open (1 High, 1 Medium). Handoff back to backend.

---

# Round 2 (re-verification after backend fixes)

Run: `pytest -q` -> **148 passed, 0 failed** (was 125 passed / 3 failed). Only the Starlette `httpx` deprecation warning.
New file: `tests/test_round2.py` (20 test cases incl. parametrized).

## Bugs fixed (verified)
- BUG-1 (High) FIXED: stock, path ids (GET/PUT/DELETE/PATCH on products/customers/orders), order `customer_id`/`product_id`, query `customer_id`/`offset` above 2**63-1 now return 422 VALIDATION_ERROR; 2**63-1 itself is accepted (GET -> 404, stock create -> 201). Huge `quantity` gives 409 INSUFFICIENT_STOCK (no 500).
- BUG-2 (Medium) FIXED: total > 9999999999.99 (single item, multi-item, and the original 10**9 x 9999999999.99 case) -> 422 VALIDATION_ERROR; stock and order table unchanged (rolled back). Total exactly 9999999999.99 -> 201.

## New behavior verified
- 101-item order -> 422 on field `items`, no stock change. 100-item order -> 201, total correct, stock decremented.

## Regression review of the fixes
- IntegrityError -> 409 in `create_order`: non-Integrity exceptions still give a clean 500 INTERNAL_ERROR with rollback (tested). IntegrityError gives 409 and rolls back (tested).
- BUG-3 (Low, remaining, design risk): the handler catches every IntegrityError, not only the stock CHECK. E.g. a FK violation (product deleted concurrently) or any future constraint is reported as a misleading `409 INSUFFICIENT_STOCK` with product 0 / 0 available (demonstrated with a simulated FK error in `test_fk_violation_masked_as_insufficient_stock_documented`). Suggest inspecting the error text for "CHECK" / `stock` and re-raising otherwise, or an atomic conditional UPDATE. Not reachable single-threaded; no data corruption.
- Quantity remains unbounded in the schema (by design, gives 409). The 100-item cap and 2**63-1 bounds are still not documented in `docs/api-contract.yaml`.
- Contract gaps from round 1 unchanged (NOT_FOUND/405 codes, regex email, case-sensitive email, price cap, no stock locking).
- No other regressions: all 128 round 1 tests pass, plus core flow (create, cancel restores stock, invalid transition 409).

## Security notes (round 2)
No stack traces, SQL or paths in any new error response; the injected "secret internal detail" exception message is not echoed in 500 bodies. The 5000-item DoS vector is closed by the 100-item cap. No auth remains out of scope.

## Verdict (round 2)
Both round 1 bugs fixed. 1 low-severity open item (BUG-3, error masking), non-blocking. 


---

# Round 3 (final re-verification of BUG-3)

Run: `python -m pytest -q` -> **150 passed, 0 failed** (was 148). Only the Starlette `httpx` deprecation warning.

## BUG-3 (Low) FIXED and verified
- Stock CHECK failure (`ck_products_stock_nonneg`, or "check constraint" + "stock") -> 409 INSUFFICIENT_STOCK with generic message "Insufficient stock for one or more products"; rollback verified, stock unchanged.
- FK violation (simulated) -> 500 INTERNAL_ERROR, rolled back, no "FOREIGN"/SQL text in the body.
- Non-stock CHECK failure (simulated `ck_order_items_quantity_positive`) -> 500 INTERNAL_ERROR, not reported as a stock error, constraint name not leaked.

## Test changes
- `test_integrity_error_in_create_order_maps_to_409`: mock message is now "CHECK constraint failed: ck_products_stock_nonneg"; also asserts the generic message.
- `test_fk_violation_masked_as_insufficient_stock_documented` replaced by `test_fk_violation_now_500_internal_error`.
- Added `test_non_stock_check_failure_not_reported_as_stock` and `test_generic_stock_check_text_variant_maps_to_409`.

## Remaining non-blocking notes
- Contract docs still do not mention the 100-item cap, 2**63-1 bounds, 9999999999.99 total cap, or NOT_FOUND / METHOD_NOT_ALLOWED codes.
- Case-sensitive email uniqueness, regex email validation, no authentication, no app-level body size limit (unchanged, by design/out of scope).
- Stock race is now handled safely (409) via the DB CHECK; not testable with the single-threaded TestClient.

## Final verdict
No open bugs. ALL CHECKS PASSED.
