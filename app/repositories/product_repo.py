from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OrderItem, Product


def add(db: Session, product: Product) -> Product:
    db.add(product)
    db.flush()
    return product


def get(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def list_(db: Session, limit: int, offset: int) -> list[Product]:
    stmt = select(Product).order_by(Product.id).limit(limit).offset(offset)
    return list(db.scalars(stmt))


def delete(db: Session, product: Product) -> None:
    db.delete(product)
    db.flush()


def is_referenced(db: Session, product_id: int) -> bool:
    stmt = select(OrderItem.id).where(OrderItem.product_id == product_id).limit(1)
    return db.scalar(stmt) is not None
