from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.users import utc_now


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    id: int | None = Field(default=None, primary_key=True)
    order_number: str = Field(max_length=32, unique=True, index=True)
    customer_id: int = Field(foreign_key="customers.id", index=True)
    store_id: int = Field(foreign_key="stores.id", index=True)
    status: str = Field(default="PENDING_PAYMENT", max_length=32, index=True)
    payment_status: str = Field(default="CREATED", max_length=32, index=True)
    total_amount_minor: int = Field(ge=0)
    currency: str = Field(max_length=12)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"
    __table_args__ = (UniqueConstraint("order_id", "product_id", name="uq_order_items_order_product"),)

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", index=True)
    product_id: int | None = Field(default=None, foreign_key="products.id", index=True)
    product_name: str = Field(max_length=200)
    unit_amount_minor: int = Field(ge=0)
    quantity: int = Field(gt=0)
    line_total_minor: int = Field(ge=0)
    currency: str = Field(max_length=12)
