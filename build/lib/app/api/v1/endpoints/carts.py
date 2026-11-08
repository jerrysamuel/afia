from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.carts import CartItemUpsert, CartRead
from app.schemas.orders import OrderRead
from app.services.catalog import CatalogConflictError, CatalogNotFoundError
from app.services.carts import checkout_cart, get_cart, remove_cart_item, upsert_cart_item
from app.services.orders import get_order

router = APIRouter(prefix="/api/v1", tags=["carts"])


def _read_cart(cart, items):
    return CartRead.model_validate({**cart.model_dump(), "items": items})


@router.get("/customers/{customer_id}/stores/{store_slug}/cart", response_model=CartRead)
def get_cart_endpoint(customer_id: int, store_slug: str, session: Session = Depends(get_session)):
    try:
        cart, items = get_cart(session, customer_id, store_slug)
        return _read_cart(cart, items)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/customers/{customer_id}/stores/{store_slug}/cart/items", response_model=CartRead)
def put_cart_item(customer_id: int, store_slug: str, data: CartItemUpsert, session: Session = Depends(get_session)):
    try:
        cart, items = upsert_cart_item(session, customer_id, store_slug, data)
        return _read_cart(cart, items)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/customers/{customer_id}/stores/{store_slug}/cart/items/{product_id}", response_model=CartRead)
def delete_cart_item(customer_id: int, store_slug: str, product_id: int, session: Session = Depends(get_session)):
    try:
        cart, items = remove_cart_item(session, customer_id, store_slug, product_id)
        return _read_cart(cart, items)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/customers/{customer_id}/stores/{store_slug}/cart/checkout", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def checkout_cart_endpoint(customer_id: int, store_slug: str, session: Session = Depends(get_session)):
    try:
        order = checkout_cart(session, customer_id, store_slug)
        _, items = get_order(session, order.id)
        return OrderRead.model_validate({**order.model_dump(), "items": items})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
