import pytest
import asyncio
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.v1.endpoints.catalog import post_merchant, post_product, post_store, put_inventory
from app.api.v1.endpoints.orders import post_customer, post_order
from app.models.orders import Order
from app.models.inventory import InventoryItem
from app.infrastructure.x402 import X402SettlementResult, X402VerificationResult
from app.models.payments import Payment, PaymentAttemptStatus, PaymentStatus
from app.schemas.catalog import CustomerCreate, InventoryUpdate, MerchantCreate, ProductCreate, StoreCreate
from app.schemas.orders import OrderCreate, OrderItemCreate
from app.services.payments import PaymentStateError, create_payment, expire_payment, process_x402_attempt, start_attempt, transition_payment


class FakeLifecycleProvider:
    def __init__(self):
        self.verify_calls = 0
        self.settle_calls = 0

    async def verify(self, payment, payload):
        self.verify_calls += 1
        return X402VerificationResult(is_valid=True, payer="0xabc")

    async def settle(self, payment, payload):
        self.settle_calls += 1
        return X402SettlementResult(success=True, transaction="0xtx", payer="0xabc", network="eip155:42220")


engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)


@pytest.fixture
def order_session():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        merchant = post_merchant(MerchantCreate(name="Ada", slug="ada"), session)
        post_store(StoreCreate(merchant_id=merchant.id, name="Ada Store", slug="ada-store"), session)
        product = post_product("ada-store", ProductCreate(name="Chair", slug="chair", amount_minor=45000000, currency="NGN"), session)
        put_inventory(product.id, InventoryUpdate(available_quantity=2), session)
        customer = post_customer(CustomerCreate(name="Buyer", email="buyer@example.com"), session)
        order = post_order(
            OrderCreate(customer_id=customer.id, store_slug="ada-store", items=[OrderItemCreate(product_id=product.id, quantity=1)]),
            session,
        )
        yield session, session.get(Order, order.id)


def test_payment_uses_authoritative_order_amount_and_is_idempotent(order_session):
    session, order = order_session
    order.total_amount_minor = 999999
    order.currency = "USD"
    session.add(order)
    session.commit()
    payment = create_payment(session, order.id, "test_provider")
    duplicate = create_payment(session, order.id, "another_provider")
    assert payment.id == duplicate.id
    assert payment.amount_minor == 999999
    assert payment.currency == "USD"
    assert len(list(session.exec(select(Payment)))) == 1


def test_attempts_increment_and_belong_to_one_payment(order_session):
    session, order = order_session
    payment = create_payment(session, order.id, "test_provider")
    first = start_attempt(session, payment.id)
    transition_payment(session, payment.id, PaymentStatus.FAILED)
    second = start_attempt(session, payment.id)
    assert first.attempt_number == 1
    assert second.attempt_number == 2
    assert first.payment_id == second.payment_id == payment.id
    assert first.status == PaymentAttemptStatus.PROCESSING


def test_invalid_payment_transitions_are_rejected(order_session):
    session, order = order_session
    payment = create_payment(session, order.id, "test_provider")
    with pytest.raises(PaymentStateError):
        transition_payment(session, payment.id, PaymentStatus.SETTLED)
    transition_payment(session, payment.id, PaymentStatus.PROCESSING)
    transition_payment(session, payment.id, PaymentStatus.VERIFIED)
    transition_payment(session, payment.id, PaymentStatus.SETTLED)
    with pytest.raises(PaymentStateError):
        transition_payment(session, payment.id, PaymentStatus.CREATED)


def test_failed_payment_cannot_settle_directly(order_session):
    session, order = order_session
    payment = create_payment(session, order.id, "test_provider")
    transition_payment(session, payment.id, PaymentStatus.PROCESSING)
    transition_payment(session, payment.id, PaymentStatus.FAILED)
    with pytest.raises(PaymentStateError):
        transition_payment(session, payment.id, PaymentStatus.SETTLED)


def test_x402_attempt_retry_does_not_settle_twice(order_session):
    session, order = order_session
    order.currency = "USD"
    session.add(order)
    session.commit()
    payment = create_payment(session, order.id, "x402")
    attempt = start_attempt(session, payment.id)
    provider = FakeLifecycleProvider()

    first = asyncio.run(process_x402_attempt(session, attempt.id, {"payload": "signed"}, provider))
    second = asyncio.run(process_x402_attempt(session, attempt.id, {"payload": "signed"}, provider))

    assert first.attempt.status == PaymentAttemptStatus.SETTLED
    assert first.payment.status == PaymentStatus.SETTLED
    assert second.attempt.status == PaymentAttemptStatus.SETTLED
    assert provider.verify_calls == 1
    assert provider.settle_calls == 1


def test_expiring_payment_releases_reserved_inventory_idempotently(order_session):
    session, order = order_session
    payment = create_payment(session, order.id, "x402")
    start_attempt(session, payment.id)
    inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == 1)).one()
    assert inventory.available_quantity == 1
    assert inventory.reserved_quantity == 1

    expired = expire_payment(session, payment.id)
    inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == 1)).one()
    assert expired.status == PaymentStatus.EXPIRED
    assert inventory.available_quantity == 2
    assert inventory.reserved_quantity == 0
    assert session.get(Order, order.id).status == "CANCELLED"

    expire_payment(session, payment.id)
    inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == 1)).one()
    assert inventory.available_quantity == 2
    assert inventory.reserved_quantity == 0
