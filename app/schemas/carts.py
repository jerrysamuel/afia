from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CartItemUpsert(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    quantity: int
    created_at: datetime
    updated_at: datetime


class CartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer_id: int
    store_id: int
    created_at: datetime
    updated_at: datetime
    items: list[CartItemRead]
