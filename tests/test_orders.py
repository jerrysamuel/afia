import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.v1.endpoints.catalog import post_merchant, post_product, post_store, put_inventory
from app.api.v1.endpoints.orders import get_order_endpoint, post_customer, post_order
from app.models.inventory import InventoryItem, InventoryMovement
from app.schemas.catalog import CustomerCreate, InventoryUpdate, MerchantCreate, ProductCreate, StoreCreate
from app.schemas.orders import OrderCreate, OrderItemCreate


engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)


@pytest.fixture
def session():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def test_order_snapshots_price_and_calculates_total(session):
    merchant = post_merchant(MerchantCreate(name="Ada", slug="ada"), session)
    post_store(StoreCreate(merchant_id=merchant.id, name="Ada Store", slug="ada-store"), session)
    product = post_product("ada-store", ProductCreate(name="Chair", slug="chair", amount_minor=45000000, currency="NGN"), session)
    put_inventory(product.id, InventoryUpdate(available_quantity=3), session)
    customer = post_customer(CustomerCreate(name="Customer", email="buyer@example.com"), session)

    order = post_order(
        OrderCreate(
            customer_id=customer.id,
            store_slug="ada-store",
            items=[OrderItemCreate(product_id=product.id, quantity=2)],
        ),
        session,
    )
    assert order.total_amount_minor == 90000000
    assert order.status == "PENDING_PAYMENT"
    assert order.payment_status == "CREATED"
    assert order.items[0].unit_amount_minor == 45000000
    inventory = session.get(InventoryItem, product.id)
    assert inventory.available_quantity == 1
    assert inventory.reserved_quantity == 2
    movement = session.exec(select(InventoryMovement)).first()
    assert movement.movement_type == "RESERVE"

    product.amount_minor = 1
    session.add(product)
    session.commit()
    fetched = get_order_endpoint(order.id, session)
    assert fetched.total_amount_minor == 90000000
    assert fetched.items[0].unit_amount_minor == 45000000


def test_order_rejects_insufficient_inventory(session):
    merchant = post_merchant(MerchantCreate(name="Ada", slug="ada"), session)
    post_store(StoreCreate(merchant_id=merchant.id, name="Ada Store", slug="ada-store"), session)
    product = post_product("ada-store", ProductCreate(name="Chair", slug="chair", amount_minor=1, currency="NGN"), session)
    put_inventory(product.id, InventoryUpdate(available_quantity=0), session)
    customer = post_customer(CustomerCreate(name="Customer", email="buyer@example.com"), session)
    with pytest.raises(HTTPException) as error:
        post_order(OrderCreate(customer_id=customer.id, store_slug="ada-store", items=[OrderItemCreate(product_id=product.id, quantity=1)]), session)
    assert error.value.status_code == 409
