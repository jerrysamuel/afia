from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.users import utc_now


class InventoryItem(SQLModel, table=True):
    __tablename__ = "inventory_items"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", unique=True, index=True)
    available_quantity: int = Field(default=0, ge=0)
    reserved_quantity: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class InventoryMovement(SQLModel, table=True):
    __tablename__ = "inventory_movements"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", index=True)
    order_id: int | None = Field(default=None, foreign_key="orders.id", index=True)
    movement_type: str = Field(max_length=32)
    quantity: int = Field(gt=0)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
