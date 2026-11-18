from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer


def add(db: Session, customer: Customer) -> Customer:
    db.add(customer)
    db.flush()
    return customer


def get(db: Session, customer_id: int) -> Customer | None:
    return db.get(Customer, customer_id)


def get_by_email(db: Session, email: str) -> Customer | None:
    return db.scalar(select(Customer).where(Customer.email == email))
