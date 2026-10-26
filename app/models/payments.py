from datetime import datetime
from enum import StrEnum

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.users import utc_now


class PaymentStatus(StrEnum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class PaymentAttemptStatus(StrEnum):
    CREATED = "CREATED"
    PROCESSING = "PROCESSING"
    VERIFIED = "VERIFIED"
    SETTLED = "SETTLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


PAYMENT_TRANSITIONS: dict[PaymentStatus, frozenset[PaymentStatus]] = {
    PaymentStatus.CREATED: frozenset({PaymentStatus.PROCESSING, PaymentStatus.EXPIRED}),
    PaymentStatus.PROCESSING: frozenset({PaymentStatus.VERIFIED, PaymentStatus.FAILED, PaymentStatus.EXPIRED}),
    PaymentStatus.VERIFIED: frozenset({PaymentStatus.SETTLED}),
    PaymentStatus.SETTLED: frozenset(),
    PaymentStatus.FAILED: frozenset({PaymentStatus.PROCESSING}),
    PaymentStatus.EXPIRED: frozenset(),
}


PAYMENT_ATTEMPT_TRANSITIONS: dict[PaymentAttemptStatus, frozenset[PaymentAttemptStatus]] = {
    PaymentAttemptStatus.CREATED: frozenset({PaymentAttemptStatus.PROCESSING, PaymentAttemptStatus.EXPIRED}),
    PaymentAttemptStatus.PROCESSING: frozenset({PaymentAttemptStatus.VERIFIED, PaymentAttemptStatus.FAILED, PaymentAttemptStatus.EXPIRED}),
    PaymentAttemptStatus.VERIFIED: frozenset({PaymentAttemptStatus.SETTLED}),
    PaymentAttemptStatus.SETTLED: frozenset(),
    PaymentAttemptStatus.FAILED: frozenset(),
    PaymentAttemptStatus.EXPIRED: frozenset(),
}


class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="orders.id", unique=True, index=True)
    amount_minor: int = Field(ge=0)
    currency: str = Field(max_length=12)
    status: PaymentStatus = Field(default=PaymentStatus.CREATED, max_length=32, index=True)
    provider: str = Field(max_length=64)
    provider_payment_id: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)


class PaymentAttempt(SQLModel, table=True):
    __tablename__ = "payment_attempts"
    __table_args__ = (UniqueConstraint("payment_id", "attempt_number", name="uq_payment_attempt_number"),)

    id: int | None = Field(default=None, primary_key=True)
    payment_id: int = Field(foreign_key="payments.id", index=True)
    attempt_number: int = Field(gt=0)
    provider: str = Field(max_length=64)
    status: PaymentAttemptStatus = Field(default=PaymentAttemptStatus.CREATED, max_length=32, index=True)
    provider_reference: str | None = Field(default=None, max_length=255)
    failure_code: str | None = Field(default=None, max_length=64)
    failure_message: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
