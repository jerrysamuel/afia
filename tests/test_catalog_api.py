import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.api.v1.endpoints.catalog import get_products, post_merchant, post_product, post_store
from app.schemas.catalog import MerchantCreate, ProductCreate, StoreCreate


engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)


def session_override():
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def reset_database():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield


@pytest.fixture
def session():
    with Session(engine) as value:
        yield value


def test_catalog_flow_uses_integer_minor_units(session):
    merchant = post_merchant(MerchantCreate(name="Ada Furniture", slug="ada-furniture"), session)
    store = post_store(StoreCreate(merchant_id=merchant.id, name="Ada Store", slug="ada-store"), session)
    product = post_product(
        "ada-store",
        ProductCreate(name="Oak Chair", slug="oak-chair", amount_minor=45000000, currency="ngn"),
        session,
    )
    assert product.amount_minor == 45000000
    assert product.currency == "NGN"
    assert len(get_products("ada-store", session)) == 1


def test_duplicate_product_slug_is_scoped_to_store(session):
    merchant = post_merchant(MerchantCreate(name="Ada Furniture", slug="ada-furniture"), session)
    post_store(StoreCreate(merchant_id=merchant.id, name="Ada Store", slug="ada-store"), session)
    post_product("ada-store", ProductCreate(name="Chair", slug="oak-chair", amount_minor=1, currency="NGN"), session)
    with pytest.raises(HTTPException, match="product slug already exists") as error:
        post_product("ada-store", ProductCreate(name="Duplicate", slug="oak-chair", amount_minor=1, currency="NGN"), session)
    assert error.value.status_code == 409
