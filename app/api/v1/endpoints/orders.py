from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.catalog import CustomerCreate, CustomerRead
from app.schemas.orders import OrderCreate, OrderItemRead, OrderRead
from app.services.catalog import CatalogConflictError, CatalogNotFoundError
from app.services.orders import cancel_order, create_customer, create_order, get_order

router = APIRouter(prefix="/api/v1", tags=["orders"])


@router.post("/customers", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def post_customer(data: CustomerCreate, session: Session = Depends(get_session)):
    try:
        return create_customer(session, data.name, data.email)
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def post_order(data: OrderCreate, session: Session = Depends(get_session)):
    try:
        order = create_order(session, data)
        _, items = get_order(session, order.id)
        return OrderRead.model_validate({**order.model_dump(), "items": items})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/orders/{order_id}", response_model=OrderRead)
def get_order_endpoint(order_id: int, session: Session = Depends(get_session)):
    try:
        order, items = get_order(session, order_id)
        return OrderRead.model_validate({**order.model_dump(), "items": items})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orders/{order_id}/cancel", response_model=OrderRead)
def cancel_order_endpoint(order_id: int, session: Session = Depends(get_session)):
    try:
        order = cancel_order(session, order_id)
        _, items = get_order(session, order.id)
        return OrderRead.model_validate({**order.model_dump(), "items": items})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
