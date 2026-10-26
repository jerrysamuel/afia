"""Tests for the x402 payment submission endpoints.

Covers both routers:
  POST /api/v1/payments/{payment_id}/attempts/{attempt_id}/x402
  POST /api/v1/agent/shopping/payments/{payment_id}/attempts/{attempt_id}/x402

All tests use an in-memory SQLite DB and a fake provider so no real
network calls or Celo facilitator credentials are needed.
"""

import asyncio

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.api.v1.endpoints.agent_shopping import shopping_post_x402_attempt
from app.api.v1.endpoints.catalog import post_merchant, post_product, post_store, put_inventory
from app.api.v1.endpoints.orders import post_customer, post_order
from app.api.v1.endpoints.payments import post_x402_attempt
from app.infrastructure.x402 import X402SettlementResult, X402VerificationResult
from app.models.orders import Order
from app.models.payments import PaymentAttemptStatus, PaymentStatus
from app.schemas.catalog import CustomerCreate, InventoryUpdate, MerchantCreate, ProductCreate, StoreCreate
from app.schemas.orders import OrderCreate, OrderItemCreate
from app.schemas.payments import PaymentAttemptCreate, PaymentCreate, X402PayloadSubmit
from app.services.payments import create_payment, get_payment, start_attempt


# ---------------------------------------------------------------------------
# Fake facilitator providers
# ---------------------------------------------------------------------------

class FakeProvider:
    """Simulates a successful verify + settle call from the Celo facilitator."""

    def __init__(
        self,
        *,
        verify_valid: bool = True,
        settle_success: bool = True,
        tx: str = "0xdeadbeef",
        payer: str = "0xbuyer",
        network: str = "eip155:11142220",
    ):
        self.verify_valid = verify_valid
        self.settle_success = settle_success
        self.tx = tx
        self.payer = payer
        self.network = network
        self.verify_calls: list[tuple] = []
        self.settle_calls: list[tuple] = []

    async def verify(self, payment, payload):
        self.verify_calls.append((payment, payload))
        return X402VerificationResult(
            is_valid=self.verify_valid,
            payer=self.payer if self.verify_valid else None,
            invalid_reason=None if self.verify_valid else "invalid_signature",
        )

    async def settle(self, payment, payload):
        self.settle_calls.append((payment, payload))
        return X402SettlementResult(
            success=self.settle_success,
            transaction=self.tx if self.settle_success else None,
            payer=self.payer,
            network=self.network,
            error_reason=None if self.settle_success else "settlement_failed",
        )


SIGNED_PAYLOAD = {"x402Version": 2, "signature": "0xabc", "resource": {"url": "https://afia.example/api"}}

# ---------------------------------------------------------------------------
# Shared DB engine + fixtures
# ---------------------------------------------------------------------------

engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)


@pytest.fixture()
def db():
    """Fresh in-memory DB for each test."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def paid_setup(db):
    """Creates merchant → store → product → customer → order → payment → attempt.

    Returns (session, payment_id, attempt_id) ready for x402 submission.
    """
    session = db
    merchant = post_merchant(MerchantCreate(name="Afia Store", slug="afia"), session)
    post_store(StoreCreate(merchant_id=merchant.id, name="Main", slug="main"), session)
    product = post_product(
        "main",
        ProductCreate(name="Widget", slug="widget", amount_minor=100, currency="USD"),
        session,
    )
    put_inventory(product.id, InventoryUpdate(available_quantity=5), session)
    customer = post_customer(CustomerCreate(name="Alice", email="alice@example.com"), session)
    order = post_order(
        OrderCreate(
            customer_id=customer.id,
            store_slug="main",
            items=[OrderItemCreate(product_id=product.id, quantity=1)],
        ),
        session,
    )
    # Refresh order to get the DB-assigned id
    order = session.get(Order, order.id)
    payment = create_payment(session, order.id, "x402")
    attempt = start_attempt(session, payment.id, "x402")
    return session, payment.id, attempt.id


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_x402_endpoint_settles_payment_and_returns_tx_hash(paid_setup):
    """Successful verify + settle → success=True with on-chain tx hash."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider(tx="0xdeadbeef")
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    result = asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    assert result.success is True
    assert result.transaction == "0xdeadbeef"
    assert result.payer == "0xbuyer"
    assert result.network == "eip155:11142220"
    assert result.error_reason is None
    assert result.invalid_reason is None


def test_x402_endpoint_transitions_attempt_and_payment_to_settled(paid_setup):
    """After a successful call both the attempt and the payment are SETTLED."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider()
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    payment, attempts = get_payment(session, payment_id)
    assert payment.status == PaymentStatus.SETTLED
    assert attempts[0].status == PaymentAttemptStatus.SETTLED
    assert attempts[0].provider_reference == "0xdeadbeef"


def test_x402_endpoint_marks_order_payment_status_settled(paid_setup):
    """Order.payment_status is updated to SETTLED after settlement."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider()
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    payment, _ = get_payment(session, payment_id)
    order = session.get(Order, payment.order_id)
    assert order.payment_status == PaymentStatus.SETTLED.value
    assert order.status == "CONFIRMED"


def test_x402_endpoint_calls_verify_then_settle_exactly_once(paid_setup):
    """The provider's verify and settle are each called exactly once per attempt."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider()
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    assert len(provider.verify_calls) == 1
    assert len(provider.settle_calls) == 1


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_x402_endpoint_is_idempotent_on_already_settled_attempt(paid_setup):
    """Calling the endpoint twice on an already-SETTLED attempt is safe.

    verify and settle are NOT called a second time — the service returns early.
    """
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider()
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))
    result = asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    assert result.success is True
    assert len(provider.verify_calls) == 1   # not called again
    assert len(provider.settle_calls) == 1   # not called again


# ---------------------------------------------------------------------------
# Verification failure
# ---------------------------------------------------------------------------

def test_x402_endpoint_returns_failure_when_verify_rejects_payload(paid_setup):
    """A payment whose signature is invalid: success=False, invalid_reason populated."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider(verify_valid=False)
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    result = asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    assert result.success is False
    assert result.invalid_reason == "invalid_signature"
    assert result.transaction is None


def test_x402_endpoint_transitions_to_failed_on_invalid_verification(paid_setup):
    """Failed verification moves both attempt and payment to FAILED."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider(verify_valid=False)
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    payment, attempts = get_payment(session, payment_id)
    assert payment.status == PaymentStatus.FAILED
    assert attempts[0].status == PaymentAttemptStatus.FAILED


def test_x402_endpoint_does_not_call_settle_when_verification_fails(paid_setup):
    """settle() must never be called if verify() rejects the payload."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider(verify_valid=False)
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    assert len(provider.settle_calls) == 0


# ---------------------------------------------------------------------------
# Settlement failure
# ---------------------------------------------------------------------------

def test_x402_endpoint_returns_failure_when_settlement_fails(paid_setup):
    """Facilitator verified OK but on-chain settlement failed → success=False."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider(settle_success=False)
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    result = asyncio.run(post_x402_attempt(payment_id, attempt_id, body, session, provider))

    assert result.success is False
    assert result.error_reason == "settlement_failed"
    assert result.transaction is None


# ---------------------------------------------------------------------------
# 404 — unknown IDs
# ---------------------------------------------------------------------------

def test_x402_endpoint_returns_404_for_unknown_attempt(paid_setup):
    """Non-existent attempt_id should surface as a 404 HTTPException."""
    from fastapi import HTTPException
    session, payment_id, _ = paid_setup
    provider = FakeProvider()
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(post_x402_attempt(payment_id, 999999, body, session, provider))

    assert exc_info.value.status_code == 404


def test_x402_endpoint_rejects_attempt_for_different_payment(paid_setup):
    """The path payment ID must own the submitted attempt."""
    from fastapi import HTTPException
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider()
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(post_x402_attempt(payment_id + 1, attempt_id, body, session, provider))

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Agent-shopping router variant
# ---------------------------------------------------------------------------

def test_agent_shopping_x402_endpoint_settles_payment(paid_setup):
    """The agent-shopping flavour of the endpoint behaves identically to the
    standard payments router — same service call, same response shape."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider(tx="0xcafe")
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    result = asyncio.run(
        shopping_post_x402_attempt(payment_id, attempt_id, body, session, provider)
    )

    assert result.success is True
    assert result.transaction == "0xcafe"
    assert result.payer == "0xbuyer"


def test_agent_shopping_x402_endpoint_settles_order(paid_setup):
    """Agent-shopping endpoint also marks order.payment_status as SETTLED."""
    session, payment_id, attempt_id = paid_setup
    provider = FakeProvider()
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    asyncio.run(shopping_post_x402_attempt(payment_id, attempt_id, body, session, provider))

    payment, _ = get_payment(session, payment_id)
    order = session.get(Order, payment.order_id)
    assert order.payment_status == PaymentStatus.SETTLED.value
    assert order.status == "CONFIRMED"


def test_agent_shopping_x402_returns_404_for_unknown_attempt(paid_setup):
    """Agent-shopping router also surfaces unknown attempt_id as 404."""
    from fastapi import HTTPException
    session, payment_id, _ = paid_setup
    provider = FakeProvider()
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(shopping_post_x402_attempt(payment_id, 999999, body, session, provider))

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Full commerce flow (search → order → pay via x402)
# ---------------------------------------------------------------------------

def test_full_commerce_flow_search_to_x402_settlement(db):
    """End-to-end: product search → order creation → payment → x402 settlement."""
    from app.api.v1.endpoints.agent_shopping import (
        shopping_create_order,
        shopping_create_payment,
        shopping_create_payment_attempt,
        shopping_search,
    )

    session = db
    merchant = post_merchant(MerchantCreate(name="E-Shop", slug="eshop"), session)
    post_store(StoreCreate(merchant_id=merchant.id, name="Online", slug="online"), session)
    product = post_product(
        "online",
        ProductCreate(name="Coffee Mug", slug="coffee-mug", amount_minor=500, currency="USD"),
        session,
    )
    put_inventory(product.id, InventoryUpdate(available_quantity=10), session)
    customer = post_customer(CustomerCreate(name="Bob", email="bob@example.com"), session)

    # Step 1: Agent searches for a product
    results = shopping_search(
        query="mug", min_amount_minor=None, max_amount_minor=None, session=session
    )
    assert any(r.id == product.id for r in results)

    # Step 2: Agent creates an order
    order = shopping_create_order(
        OrderCreate(
            customer_id=customer.id,
            store_slug="online",
            items=[OrderItemCreate(product_id=product.id, quantity=2)],
        ),
        session,
    )
    assert order.total_amount_minor == 1000  # 2 × $5.00

    # Step 3: Agent creates a payment
    payment = shopping_create_payment(order.id, PaymentCreate(provider="x402"), session)
    assert payment.status == "CREATED"
    assert payment.amount_minor == 1000

    # Step 4: Agent starts a payment attempt (PROCESSING)
    payment_with_attempt = shopping_create_payment_attempt(
        payment.id, PaymentAttemptCreate(provider="x402"), session
    )
    assert payment_with_attempt.status == "PROCESSING"
    attempt_id = payment_with_attempt.attempts[0].id

    # Step 5: Agent submits signed x402 payload → verify + settle on Celo
    provider = FakeProvider(tx="0xfinalTx")
    body = X402PayloadSubmit(payload=SIGNED_PAYLOAD)
    result = asyncio.run(
        shopping_post_x402_attempt(payment.id, attempt_id, body, session, provider)
    )

    assert result.success is True
    assert result.transaction == "0xfinalTx"
    assert result.attempt.status == "SETTLED"
    assert result.payment.status == "SETTLED"
