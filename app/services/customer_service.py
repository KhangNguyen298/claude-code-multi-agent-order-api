from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import CustomerNotFound, EmailAlreadyExists
from app.models import Customer
from app.repositories import customer_repo
from app.schemas.customer import CustomerCreate


def create_customer(db: Session, data: CustomerCreate) -> Customer:
    if customer_repo.get_by_email(db, data.email) is not None:
        raise EmailAlreadyExists(data.email)
    customer = Customer(name=data.name, email=data.email)
    try:
        customer_repo.add(db, customer)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise EmailAlreadyExists(data.email)
    except Exception:
        db.rollback()
        raise
    return customer


def get_customer(db: Session, customer_id: int) -> Customer:
    customer = customer_repo.get(db, customer_id)
    if customer is None:
        raise CustomerNotFound(customer_id)
    return customer
