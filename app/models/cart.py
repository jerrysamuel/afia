from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.users import utc_now


class Cart(SQLModel, table=True):
    __tablename__ = "carts"
    __table_args__ = (UniqueConstraint("customer_id", "store_id", name="uq_carts_customer_store"),)

    id: int | None = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id", index=True)
    store_id: int = Field(foreign_key="stores.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "product_id", name="uq_cart_items_cart_product"),)

    id: int | None = Field(default=None, primary_key=True)
    cart_id: int = Field(foreign_key="carts.id", index=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    quantity: int = Field(gt=0)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
