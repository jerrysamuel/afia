from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.inventory import InventoryItem, InventoryMovement
from app.models.orders import Order, OrderItem
from app.models.products import Product
from app.models.users import Customer
from app.schemas.orders import OrderCreate
from app.services.catalog import CatalogConflictError, CatalogNotFoundError, get_store_by_slug


def create_customer(session: Session, name: str, email: str) -> Customer:
    customer = Customer(name=name, email=email.lower())
    session.add(customer)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogConflictError("customer email already exists") from exc
    session.refresh(customer)
    return customer


def create_order(session: Session, data: OrderCreate) -> Order:
    if session.get(Customer, data.customer_id) is None:
        raise CatalogNotFoundError("customer not found")
    store = get_store_by_slug(session, data.store_slug)
    if len({item.product_id for item in data.items}) != len(data.items):
        raise CatalogConflictError("each product may appear only once in an order")

    products: list[tuple[Product, int]] = []
    for requested in data.items:
        product = session.get(Product, requested.product_id)
        if product is None or product.store_id != store.id:
            raise CatalogNotFoundError("product not found in store")
        inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == product.id)).first()
        if inventory is None or inventory.available_quantity < requested.quantity:
            raise CatalogConflictError(f"insufficient inventory for product {product.id}")
        products.append((product, requested.quantity))

    currencies = {product.currency for product, _ in products}
    if len(currencies) != 1:
        raise CatalogConflictError("all order items must use the same currency")
    currency = currencies.pop()
    order = Order(
        order_number=f"AF-{uuid4().hex[:12].upper()}",
        customer_id=data.customer_id,
        store_id=store.id,
        total_amount_minor=sum(product.amount_minor * quantity for product, quantity in products),
        currency=currency,
    )
    session.add(order)
    session.flush()
    for product, quantity in products:
        inventory = session.exec(select(InventoryItem).where(InventoryItem.product_id == product.id)).one()
        inventory.available_quantity -= quantity
        inventory.reserved_quantity += quantity
        inventory.updated_at = datetime.now(timezone.utc)
        session.add(inventory)
        session.add(
            InventoryMovement(
                product_id=product.id,
                order_id=order.id,
                movement_type="RESERVE",
                quantity=quantity,
            )
        )
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                unit_amount_minor=product.amount_minor,
                quantity=quantity,
                line_total_minor=product.amount_minor * quantity,
                currency=product.currency,
            )
        )
    session.commit()
    session.refresh(order)
    return order


def get_order(session: Session, order_id: int) -> tuple[Order, list[OrderItem]]:
    order = session.get(Order, order_id)
    if order is None:
        raise CatalogNotFoundError("order not found")
    items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)))
    return order, items


def cancel_order(session: Session, order_id: int) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise CatalogNotFoundError("order not found")
    if order.status == "CANCELLED":
        return order
    if order.payment_status == "SETTLED":
        raise CatalogConflictError("settled orders cannot be cancelled")

    release_order_reservation(session, order.id)
    order.status = "CANCELLED"
    order.updated_at = datetime.now(timezone.utc)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def release_order_reservation(session: Session, order_id: int) -> None:
    """Return an order's reserved inventory exactly once.

    The RESTORE movement makes this operation safe to repeat after retries or
    duplicate cancellation/expiry requests.
    """
    reservations = list(
        session.exec(
            select(InventoryMovement).where(
                InventoryMovement.order_id == order_id,
                InventoryMovement.movement_type == "RESERVE",
            )
        )
    )
    for reservation in reservations:
        restored = session.exec(
            select(InventoryMovement).where(
                InventoryMovement.order_id == order_id,
                InventoryMovement.product_id == reservation.product_id,
                InventoryMovement.movement_type == "RESTORE",
            )
        ).first()
        if restored is not None:
            continue
        inventory = session.exec(
            select(InventoryItem).where(InventoryItem.product_id == reservation.product_id)
        ).one()
        inventory.available_quantity += reservation.quantity
        inventory.reserved_quantity -= reservation.quantity
        inventory.updated_at = datetime.now(timezone.utc)
        session.add(inventory)
        session.add(
            InventoryMovement(
                product_id=reservation.product_id,
                order_id=order_id,
                movement_type="RESTORE",
                quantity=reservation.quantity,
            )
        )
