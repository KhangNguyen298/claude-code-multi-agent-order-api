from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import OrderStatus
from app.schemas.common import MoneyOut, as_utc

StatusLiteral = Literal["PENDING", "PAID", "SHIPPED", "DELIVERED", "CANCELLED"]


class OrderItemCreate(BaseModel):
    product_id: int = Field(ge=1, le=2**63 - 1)
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: int = Field(ge=1, le=2**63 - 1)
    items: list[OrderItemCreate] = Field(min_length=1, max_length=100)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[OrderItemCreate]):
        ids = [i.product_id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Product ids must be unique within items")
        return items


class OrderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: int
    unit_price: MoneyOut


class Order(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    items: list[OrderItem]
    status: StatusLiteral
    total: MoneyOut
    created_at: datetime

    @field_validator("status", mode="before")
    @classmethod
    def _status(cls, v):
        return v.value if isinstance(v, OrderStatus) else v

    @field_validator("created_at")
    @classmethod
    def _utc(cls, v: datetime):
        return as_utc(v)


class OrderStatusUpdate(BaseModel):
    status: StatusLiteral
