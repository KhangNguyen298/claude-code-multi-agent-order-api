from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Order, OrderStatus


def add(db: Session, order: Order) -> Order:
    db.add(order)
    db.flush()
    return order


def get(db: Session, order_id: int) -> Order | None:
    stmt = select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    return db.scalar(stmt)


def list_(
    db: Session,
    status: OrderStatus | None,
    customer_id: int | None,
    limit: int,
    offset: int,
) -> list[Order]:
    stmt = select(Order).options(selectinload(Order.items))
    if status is not None:
        stmt = stmt.where(Order.status == status)
    if customer_id is not None:
        stmt = stmt.where(Order.customer_id == customer_id)
    stmt = stmt.order_by(Order.id).limit(limit).offset(offset)
    return list(db.scalars(stmt))
