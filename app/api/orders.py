from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import OrderStatus
from app.schemas.order import Order, OrderCreate, OrderStatusUpdate
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])
DB = Annotated[Session, Depends(get_db)]
OrderId = Annotated[int, Path(ge=1, le=2**63 - 1)]


@router.post("", response_model=Order, status_code=201)
def create_order(data: OrderCreate, db: DB):
    return order_service.create_order(db, data)


@router.get("", response_model=list[Order])
def list_orders(
    db: DB,
    status: OrderStatus | None = None,
    customer_id: Annotated[int | None, Query(ge=1, le=2**63 - 1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
):
    return order_service.list_orders(db, status, customer_id, limit, offset)


@router.get("/{order_id}", response_model=Order)
def get_order(order_id: OrderId, db: DB):
    return order_service.get_order(db, order_id)


@router.patch("/{order_id}/status", response_model=Order)
def update_order_status(order_id: OrderId, data: OrderStatusUpdate, db: DB):
    return order_service.update_status(db, order_id, OrderStatus(data.status))
