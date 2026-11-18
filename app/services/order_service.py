from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    AppError,
    CustomerNotFound,
    InsufficientStock,
    InvalidStatusTransition,
    OrderNotFound,
    ProductNotFound,
)
from app.models import Order, OrderItem, OrderStatus
from app.repositories import customer_repo, order_repo, product_repo
from app.schemas.order import OrderCreate

MAX_TOTAL = Decimal("9999999999.99")  # Money column limit (12 digits, 2 decimals)

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


def create_order(db: Session, data: OrderCreate) -> Order:
    if customer_repo.get(db, data.customer_id) is None:
        raise CustomerNotFound(data.customer_id)

    # Validate everything first (existence, then stock) before mutating.
    lines = []
    for item in data.items:
        product = product_repo.get(db, item.product_id)
        if product is None:
            raise ProductNotFound(item.product_id)
        lines.append((product, item.quantity))
    for product, quantity in lines:
        if quantity > product.stock:
            raise InsufficientStock(product.id, product.stock)

    try:
        order = Order(customer_id=data.customer_id, status=OrderStatus.PENDING)
        total = Decimal("0.00")
        for product, quantity in lines:
            product.stock -= quantity
            order.items.append(
                OrderItem(product_id=product.id, quantity=quantity, unit_price=product.price)
            )
            total += product.price * quantity
        if total > MAX_TOTAL:
            raise AppError(
                "Order total exceeds the maximum allowed",
                status_code=422,
                code="VALIDATION_ERROR",
            )
        order.total = total
        order_repo.add(db, order)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        msg = str(getattr(exc, "orig", exc)).lower()
        if "ck_products_stock_nonneg" in msg or (
            "check constraint" in msg and "stock" in msg
        ):
            # Concurrent order consumed the stock after our pre-check.
            raise AppError(
                "Insufficient stock for one or more products",
                status_code=409,
                code="INSUFFICIENT_STOCK",
            ) from exc
        raise  # FK or other integrity errors -> 500 INTERNAL_ERROR
    except Exception:
        db.rollback()
        raise
    return order


def get_order(db: Session, order_id: int) -> Order:
    order = order_repo.get(db, order_id)
    if order is None:
        raise OrderNotFound(order_id)
    return order


def list_orders(
    db: Session,
    status: OrderStatus | None,
    customer_id: int | None,
    limit: int,
    offset: int,
) -> list[Order]:
    return order_repo.list_(db, status, customer_id, limit, offset)


def update_status(db: Session, order_id: int, new_status: OrderStatus) -> Order:
    order = get_order(db, order_id)
    current = OrderStatus(order.status)
    if new_status not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStatusTransition(current.value, new_status.value)
    try:
        if new_status == OrderStatus.CANCELLED:
            for item in order.items:
                product = product_repo.get(db, item.product_id)
                if product is not None:
                    product.stock += item.quantity
        order.status = new_status
        db.commit()
    except Exception:
        db.rollback()
        raise
    return order
