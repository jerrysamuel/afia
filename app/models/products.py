from datetime import datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.users import utc_now


class Store(SQLModel, table=True):
    __tablename__ = "stores"

    id: int | None = Field(default=None, primary_key=True)
    merchant_id: int = Field(foreign_key="merchants.id", index=True)
    name: str = Field(max_length=200)
    slug: str = Field(max_length=100, unique=True, index=True)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="other", max_length=64)
    template_id: str = Field(default="default", max_length=100)
    theme_config: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    sections_config: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    settings_config: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class Product(SQLModel, table=True):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("store_id", "slug", name="uq_products_store_slug"),)

    id: int | None = Field(default=None, primary_key=True)
    store_id: int = Field(foreign_key="stores.id", index=True)
    name: str = Field(max_length=200)
    slug: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=100, index=True)
    attributes: dict[str, object] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    amount_minor: int = Field(ge=0)
    currency: str = Field(max_length=12)
    product_type: str = Field(default="physical", max_length=16)
    digital_url: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
