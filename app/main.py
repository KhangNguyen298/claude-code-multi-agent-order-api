import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import customers, orders, products
from app.core.errors import AppError
from app.db.session import init_db

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Order Management API", version="1.0.0", lifespan=lifespan)
app.include_router(products.router)
app.include_router(customers.router)
app.include_router(orders.router)


def _error(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body: dict = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


@app.exception_handler(AppError)
async def app_error_handler(_req: Request, exc: AppError):
    return _error(exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def validation_handler(_req: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        loc = [str(p) for p in err["loc"] if p not in ("body", "query", "path")]
        details.append({"field": ".".join(loc), "message": err["msg"]})
    return _error(422, "VALIDATION_ERROR", "Request validation failed", details)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_req: Request, exc: StarletteHTTPException):
    # Contract enum has no generic NOT_FOUND / METHOD_NOT_ALLOWED code; use BAD_REQUEST.
    code = "BAD_REQUEST" if exc.status_code < 500 else "INTERNAL_ERROR"
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def unhandled_handler(_req: Request, exc: Exception):
    logger.exception("Unhandled error", exc_info=exc)
    return _error(500, "INTERNAL_ERROR", "Internal server error")
