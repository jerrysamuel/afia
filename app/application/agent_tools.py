from typing import Any

from sqlmodel import Session

from app.infrastructure.x402 import X402PaymentProvider
from app.schemas.orders import OrderCreate
from app.services.orders import create_order, get_order
from app.services.catalog import search_products
from app.services.payments import (
    create_payment,
    get_payment,
    process_x402_attempt,
    start_attempt,
)


def agent_search_products(session: Session, **filters):
    return search_products(session, **filters)


def agent_get_order(session: Session, order_id: int):
    return get_order(session, order_id)


def agent_create_order(session: Session, data: OrderCreate):
    return create_order(session, data)


# ---------------------------------------------------------------------------
# Payment tools
# ---------------------------------------------------------------------------

def agent_create_payment(session: Session, order_id: int, provider: str = "x402"):
    """Initialise a Payment record for *order_id*.

    Idempotent — returns the existing Payment if one already exists for the
    order.  The ``provider`` should always be ``"x402"`` for Celo payments.
    """
    return create_payment(session, order_id, provider)


def agent_get_payment(session: Session, payment_id: int):
    """Return the Payment and its list of PaymentAttempts."""
    return get_payment(session, payment_id)


def agent_start_attempt(session: Session, payment_id: int, provider: str | None = None):
    """Open a new PaymentAttempt and move the payment to PROCESSING.

    The agent should call this before constructing and signing the x402
    PaymentPayload on Celo.  Returns the new PaymentAttempt row.
    """
    return start_attempt(session, payment_id, provider)


async def agent_submit_x402(
    session: Session,
    attempt_id: int,
    payload: dict[str, Any],
    provider: X402PaymentProvider,
):
    """Verify and settle a signed x402 PaymentPayload on Celo.

    ``payload`` is the decoded PaymentPayload dict the agent built from its
    wallet signature.  On success the attempt and payment move to SETTLED and
    the on-chain transaction hash is available on the returned result.
    """
    return await process_x402_attempt(session, attempt_id, payload, provider)
