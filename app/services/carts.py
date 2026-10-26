from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.cart import Cart, CartItem
from app.models.products import Product
from app.models.users import Customer
from app.schemas.carts import CartItemUpsert
from app.schemas.orders import OrderCreate, OrderItemCreate
from app.services.catalog import CatalogConflictError, CatalogNotFoundError, get_store_by_slug
from app.services.orders import create_order


def get_or_create_cart(session: Session, customer_id: int, store_slug: str) -> Cart:
    if session.get(Customer, customer_id) is None:
        raise CatalogNotFoundError("customer not found")
    store = get_store_by_slug(session, store_slug)
    cart = session.exec(select(Cart).where(Cart.customer_id == customer_id, Cart.store_id == store.id)).first()
    if cart is not None:
        return cart
    cart = Cart(customer_id=customer_id, store_id=store.id)
    session.add(cart)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        cart = session.exec(select(Cart).where(Cart.customer_id == customer_id, Cart.store_id == store.id)).first()
        if cart is not None:
            return cart
        raise CatalogConflictError("cart could not be created") from exc
    session.refresh(cart)
    return cart


def get_cart(session: Session, customer_id: int, store_slug: str) -> tuple[Cart, list[CartItem]]:
    cart = get_or_create_cart(session, customer_id, store_slug)
    items = list(session.exec(select(CartItem).where(CartItem.cart_id == cart.id).order_by(CartItem.id)))
    return cart, items


def upsert_cart_item(session: Session, customer_id: int, store_slug: str, data: CartItemUpsert) -> tuple[Cart, list[CartItem]]:
    cart, _ = get_cart(session, customer_id, store_slug)
    product = session.get(Product, data.product_id)
    if product is None or product.store_id != cart.store_id:
        raise CatalogNotFoundError("product not found in store")
    item = session.exec(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == data.product_id)).first()
    if item is None:
        item = CartItem(cart_id=cart.id, product_id=data.product_id, quantity=data.quantity)
    else:
        item.quantity = data.quantity
        item.updated_at = datetime.now(timezone.utc)
    cart.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.add(cart)
    session.commit()
    return get_cart(session, customer_id, store_slug)


def remove_cart_item(session: Session, customer_id: int, store_slug: str, product_id: int) -> tuple[Cart, list[CartItem]]:
    cart, _ = get_cart(session, customer_id, store_slug)
    item = session.exec(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id)).first()
    if item is None:
        raise CatalogNotFoundError("cart item not found")
    session.delete(item)
    cart.updated_at = datetime.now(timezone.utc)
    session.add(cart)
    session.commit()
    return get_cart(session, customer_id, store_slug)


def checkout_cart(session: Session, customer_id: int, store_slug: str):
    cart, items = get_cart(session, customer_id, store_slug)
    if not items:
        raise CatalogConflictError("cannot checkout an empty cart")
    order = create_order(
        session,
        OrderCreate(
            customer_id=customer_id,
            store_slug=store_slug,
            items=[OrderItemCreate(product_id=item.product_id, quantity=item.quantity) for item in items],
        ),
    )
    for item in items:
        session.delete(item)
    session.commit()
    return order
