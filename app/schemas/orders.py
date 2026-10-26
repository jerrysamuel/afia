from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: int = Field(gt=0)
    store_slug: str = Field(min_length=1, max_length=100)
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int | None
    product_name: str
    unit_amount_minor: int
    quantity: int
    line_total_minor: int
    currency: str


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_number: str
    customer_id: int
    store_id: int
    status: str
    payment_status: str
    total_amount_minor: int
    currency: str
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]

