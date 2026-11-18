from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.customer import Customer, CustomerCreate
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["customers"])
DB = Annotated[Session, Depends(get_db)]


@router.post("", response_model=Customer, status_code=201)
def create_customer(data: CustomerCreate, db: DB):
    return customer_service.create_customer(db, data)


@router.get("/{customer_id}", response_model=Customer)
def get_customer(customer_id: Annotated[int, Path(ge=1, le=2**63 - 1)], db: DB):
    return customer_service.get_customer(db, customer_id)
