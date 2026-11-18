from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.product import Product, ProductCreate
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])
DB = Annotated[Session, Depends(get_db)]
ProductId = Annotated[int, Path(ge=1, le=2**63 - 1)]


@router.post("", response_model=Product, status_code=201)
def create_product(data: ProductCreate, db: DB):
    return product_service.create_product(db, data)


@router.get("", response_model=list[Product])
def list_products(
    db: DB,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
):
    return product_service.list_products(db, limit, offset)


@router.get("/{product_id}", response_model=Product)
def get_product(product_id: ProductId, db: DB):
    return product_service.get_product(db, product_id)


@router.put("/{product_id}", response_model=Product)
def update_product(product_id: ProductId, data: ProductCreate, db: DB):
    return product_service.update_product(db, product_id, data)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: ProductId, db: DB):
    product_service.delete_product(db, product_id)
    return Response(status_code=204)
