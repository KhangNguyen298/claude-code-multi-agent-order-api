from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ProductInUse, ProductNotFound
from app.models import Product
from app.repositories import product_repo
from app.schemas.product import ProductCreate


def create_product(db: Session, data: ProductCreate) -> Product:
    product = Product(name=data.name, price=data.price, stock=data.stock)
    try:
        product_repo.add(db, product)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return product


def get_product(db: Session, product_id: int) -> Product:
    product = product_repo.get(db, product_id)
    if product is None:
        raise ProductNotFound(product_id)
    return product


def list_products(db: Session, limit: int, offset: int) -> list[Product]:
    return product_repo.list_(db, limit, offset)


def update_product(db: Session, product_id: int, data: ProductCreate) -> Product:
    product = get_product(db, product_id)
    try:
        product.name = data.name
        product.price = data.price
        product.stock = data.stock
        db.commit()
    except Exception:
        db.rollback()
        raise
    return product


def delete_product(db: Session, product_id: int) -> None:
    product = get_product(db, product_id)
    if product_repo.is_referenced(db, product_id):
        raise ProductInUse(product_id)
    try:
        product_repo.delete(db, product)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProductInUse(product_id)
    except Exception:
        db.rollback()
        raise
