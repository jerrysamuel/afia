from sqlmodel import Session, SQLModel, create_engine

from app.api.v1.endpoints.agent_shopping import (
    shopping_availability,
    shopping_create_order,
    shopping_create_payment,
    shopping_create_payment_attempt,
    shopping_product,
    shopping_search,
)
from app.api.v1.endpoints.catalog import post_merchant, post_product, post_store, put_inventory
from app.api.v1.endpoints.orders import post_customer
from app.schemas.catalog import CustomerCreate, InventoryUpdate, MerchantCreate, ProductCreate, StoreCreate
from app.schemas.orders import OrderCreate, OrderItemCreate
from app.schemas.payments import PaymentAttemptCreate, PaymentCreate


def test_agent_shopping_route_covers_commerce_flow():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        merchant = post_merchant(MerchantCreate(name="Ada", slug="ada"), session)
        post_store(StoreCreate(merchant_id=merchant.id, name="Ada Store", slug="ada-store"), session)
        product = post_product("ada-store", ProductCreate(name="Dining Table", slug="dining-table", amount_minor=50000, currency="USD"), session)
        put_inventory(product.id, InventoryUpdate(available_quantity=1), session)
        customer = post_customer(CustomerCreate(name="Buyer", email="buyer@example.com"), session)

        assert shopping_search(query="table", min_amount_minor=None, max_amount_minor=None, session=session)[0].id == product.id
        assert shopping_product(product.id, session).id == product.id
        assert shopping_availability(product.id, session).available_quantity == 1

        order = shopping_create_order(
            OrderCreate(customer_id=customer.id, store_slug="ada-store", items=[OrderItemCreate(product_id=product.id, quantity=1)]),
            session,
        )
        payment = shopping_create_payment(order.id, PaymentCreate(provider="future_provider"), session)
        assert payment.order_id == order.id
        assert payment.amount_minor == 50000

        payment_with_attempt = shopping_create_payment_attempt(
            payment.id,
            PaymentAttemptCreate(provider="future_provider"),
            session,
        )
        assert payment_with_attempt.status == "PROCESSING"
        assert len(payment_with_attempt.attempts) == 1
