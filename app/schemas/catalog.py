from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MerchantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    wallet_address: str | None = Field(default=None, pattern=r"^0x[a-fA-F0-9]{40}$")


class MerchantRead(MerchantCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class StoreCreate(BaseModel):
    merchant_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="other", max_length=64)
    template_id: str = Field(default="default", max_length=100)
    theme_config: dict[str, object] = Field(default_factory=dict)
    sections_config: dict[str, object] = Field(default_factory=dict)
    settings_config: dict[str, object] = Field(default_factory=dict)


class StoreRead(StoreCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=100)
    attributes: dict[str, object] = Field(default_factory=dict)
    amount_minor: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=12)
    product_type: str = Field(default="physical", pattern=r"^(physical|digital)$")
    digital_url: str | None = Field(default=None, max_length=2000)
    published: bool = True

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        value = value.upper()
        if not value.isalnum():
            raise ValueError("currency must contain only letters and numbers")
        return value


class ProductRead(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    store_id: int
    created_at: datetime
    updated_at: datetime


class InventoryUpdate(BaseModel):
    available_quantity: int = Field(ge=0)


class InventoryRead(InventoryUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    reserved_quantity: int
    updated_at: datetime


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)


class CustomerRead(CustomerCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
