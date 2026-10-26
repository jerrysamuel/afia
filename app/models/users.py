from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Merchant(SQLModel, table=True):
    __tablename__ = "merchants"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    slug: str = Field(max_length=100, unique=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)


class Customer(SQLModel, table=True):
    __tablename__ = "customers"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    email: str = Field(max_length=320, unique=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
