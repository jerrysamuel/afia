from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    provider: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")


class PaymentAttemptCreate(BaseModel):
    provider: str | None = Field(default=None, min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")


class PaymentAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    payment_id: int
    attempt_number: int
    provider: str
    status: str
    provider_reference: str | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    amount_minor: int
    currency: str
    status: str
    provider: str
    provider_payment_id: str | None
    created_at: datetime
    updated_at: datetime
    attempts: list[PaymentAttemptRead]


class X402PayloadSubmit(BaseModel):
    """The signed x402 payment payload submitted by the paying agent.

    The ``payload`` field must be a valid x402 PaymentPayload-compatible
    dict (the value the agent attaches as the X-PAYMENT header decoded to
    JSON). It is passed directly to X402PaymentProvider.verify / .settle.
    """

    payload: dict[str, Any]


class X402AttemptResultRead(BaseModel):
    """Response returned after verify + settle of an x402 attempt."""

    model_config = ConfigDict(from_attributes=True)

    success: bool
    transaction: str | None = None   # on-chain Celo tx hash
    payer: str | None = None         # payer's wallet address
    network: str | None = None       # e.g. "eip155:42220"
    error_reason: str | None = None  # set when success=False
    invalid_reason: str | None = None  # set when verification failed
    attempt: PaymentAttemptRead
    payment: PaymentRead
