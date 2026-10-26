from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.application.agent_tools import agent_create_order, agent_get_order, agent_search_products
from app.db.session import get_session
from app.schemas.catalog import ProductRead
from app.schemas.orders import OrderCreate, OrderRead
from app.services.catalog import CatalogConflictError, CatalogNotFoundError

router = APIRouter(prefix="/api/v1/agent", tags=["agent-tools"])


@router.get("/products/search", response_model=list[ProductRead])
def agent_search(
    query: str | None = Query(default=None, max_length=200),
    store_slug: str | None = None,
    currency: str | None = None,
    available_only: bool = False,
    session: Session = Depends(get_session),
):
    try:
        return agent_search_products(session, query=query, store_slug=store_slug, currency=currency, available_only=available_only)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orders", response_model=OrderRead, status_code=201)
def agent_order(data: OrderCreate, session: Session = Depends(get_session)):
    try:
        order = agent_create_order(session, data)
        _, items = agent_get_order(session, order.id)
        return OrderRead.model_validate({**order.model_dump(), "items": items})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/orders/{order_id}", response_model=OrderRead)
def agent_order_status(order_id: int, session: Session = Depends(get_session)):
    try:
        order, items = agent_get_order(session, order_id)
        return OrderRead.model_validate({**order.model_dump(), "items": items})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
