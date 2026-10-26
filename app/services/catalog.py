from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.inventory import InventoryItem
from app.models.products import Product, Store
from app.models.users import Merchant
from app.schemas.catalog import InventoryUpdate, MerchantCreate, ProductCreate, StoreCreate


class CatalogConflictError(Exception):
    pass


class CatalogNotFoundError(Exception):
    pass


def create_merchant(session: Session, data: MerchantCreate) -> Merchant:
    merchant = Merchant.model_validate(data)
    session.add(merchant)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogConflictError("merchant slug already exists") from exc
    session.refresh(merchant)
    return merchant


def create_store(session: Session, data: StoreCreate) -> Store:
    if session.get(Merchant, data.merchant_id) is None:
        raise CatalogNotFoundError("merchant not found")
    store = Store.model_validate(data)
    session.add(store)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogConflictError("store slug already exists") from exc
    session.refresh(store)
    return store


def get_store_by_slug(session: Session, slug: str) -> Store:
    store = session.exec(select(Store).where(Store.slug == slug)).first()
    if store is None:
        raise CatalogNotFoundError("store not found")
    return store


def get_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise CatalogNotFoundError("product not found")
    return product


def get_inventory(session: Session, product_id: int) -> InventoryItem:
    get_product(session, product_id)
    inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == product_id)).first()
    if inventory is None:
        raise CatalogNotFoundError("inventory not found")
    return inventory


def create_product(session: Session, store_slug: str, data: ProductCreate) -> Product:
    store = get_store_by_slug(session, store_slug)
    product = Product(store_id=store.id, **data.model_dump())
    session.add(product)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogConflictError("product slug already exists in this store") from exc
    session.refresh(product)
    return product


def list_products(session: Session, store_slug: str) -> list[Product]:
    store = get_store_by_slug(session, store_slug)
    return list(session.exec(select(Product).where(Product.store_id == store.id).order_by(Product.id)))


def search_products(
    session: Session,
    query: str | None = None,
    store_slug: str | None = None,
    currency: str | None = None,
    min_amount_minor: int | None = None,
    max_amount_minor: int | None = None,
    available_only: bool = False,
) -> list[Product]:
    statement = select(Product)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where((Product.name.ilike(pattern)) | (Product.description.ilike(pattern)))
    if store_slug:
        store = get_store_by_slug(session, store_slug)
        statement = statement.where(Product.store_id == store.id)
    if currency:
        statement = statement.where(Product.currency == currency.upper())
    if min_amount_minor is not None:
        statement = statement.where(Product.amount_minor >= min_amount_minor)
    if max_amount_minor is not None:
        statement = statement.where(Product.amount_minor <= max_amount_minor)
    products = list(session.exec(statement.order_by(Product.id)))
    if not available_only:
        return products
    available_products = []
    for product in products:
        inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == product.id)).first()
        if inventory is not None and inventory.available_quantity > 0:
            available_products.append(product)
    return available_products


def update_inventory(session: Session, product_id: int, data: InventoryUpdate) -> InventoryItem:
    if session.get(Product, product_id) is None:
        raise CatalogNotFoundError("product not found")
    inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == product_id)).first()
    now = datetime.now(timezone.utc)
    if inventory is None:
        inventory = InventoryItem(product_id=product_id, **data.model_dump())
    else:
        if data.available_quantity < inventory.reserved_quantity:
            raise CatalogConflictError("available quantity cannot be below reserved quantity")
        inventory.available_quantity = data.available_quantity
        inventory.updated_at = now
    session.add(inventory)
    session.commit()
    session.refresh(inventory)
    return inventory
