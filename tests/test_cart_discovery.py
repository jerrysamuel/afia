from sqlmodel import Session, SQLModel, create_engine, select

from app.application.agent_tools import agent_search_products
from app.api.v1.endpoints.catalog import post_merchant, post_product, post_store, put_inventory
from app.api.v1.endpoints.carts import checkout_cart_endpoint, put_cart_item
from app.api.v1.endpoints.orders import post_customer
from app.models.cart import CartItem
from app.models.inventory import InventoryItem
from app.schemas.catalog import CustomerCreate, InventoryUpdate, MerchantCreate, ProductCreate, StoreCreate
from app.schemas.carts import CartItemUpsert


def test_cart_checkout_and_agent_search():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        merchant = post_merchant(MerchantCreate(name="Ada", slug="ada"), session)
        post_store(StoreCreate(merchant_id=merchant.id, name="Ada Store", slug="ada-store"), session)
        product = post_product("ada-store", ProductCreate(name="Oak Chair", slug="oak-chair", amount_minor=100, currency="NGN", description="solid wood"), session)
        put_inventory(product.id, InventoryUpdate(available_quantity=2), session)
        customer = post_customer(CustomerCreate(name="Buyer", email="buyer@example.com"), session)
        results = agent_search_products(session, query="wood", currency="ngn", available_only=True)
        assert [item.id for item in results] == [product.id]
        put_cart_item(customer.id, "ada-store", CartItemUpsert(product_id=product.id, quantity=1), session)
        order = checkout_cart_endpoint(customer.id, "ada-store", session)
        assert order.total_amount_minor == 100
        assert session.exec(select(CartItem)).first() is None
        inventory = session.get(InventoryItem, product.id)
        assert inventory.available_quantity == 1
