from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.catalog import (
    InventoryRead,
    InventoryUpdate,
    MerchantCreate,
    MerchantRead,
    ProductCreate,
    ProductRead,
    StoreCreate,
    StoreRead,
)
from app.services.catalog import (
    CatalogConflictError,
    CatalogNotFoundError,
    create_merchant,
    create_product,
    create_store,
    get_store_by_slug,
    list_products,
    search_products,
    update_inventory,
)

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.post("/merchants", response_model=MerchantRead, status_code=status.HTTP_201_CREATED)
def post_merchant(data: MerchantCreate, session: Session = Depends(get_session)):
    try:
        return create_merchant(session, data)
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/stores", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
def post_store(data: StoreCreate, session: Session = Depends(get_session)):
    try:
        return create_store(session, data)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/stores/{slug}", response_model=StoreRead)
def get_store(slug: str, session: Session = Depends(get_session)):
    try:
        return get_store_by_slug(session, slug)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/stores/{slug}/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def post_product(slug: str, data: ProductCreate, session: Session = Depends(get_session)):
    try:
        return create_product(session, slug, data)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/stores/{slug}/products", response_model=list[ProductRead])
def get_products(slug: str, session: Session = Depends(get_session)):
    try:
        return list_products(session, slug)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/products/search", response_model=list[ProductRead])
def search_products_endpoint(
    query: str | None = Query(default=None, min_length=1, max_length=200),
    store_slug: str | None = Query(default=None),
    currency: str | None = Query(default=None, min_length=3, max_length=12),
    min_amount_minor: int | None = Query(default=None, ge=0),
    max_amount_minor: int | None = Query(default=None, ge=0),
    available_only: bool = False,
    session: Session = Depends(get_session),
):
    try:
        return search_products(session, query, store_slug, currency, min_amount_minor, max_amount_minor, available_only)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/products/{product_id}/inventory", response_model=InventoryRead)
def put_inventory(product_id: int, data: InventoryUpdate, session: Session = Depends(get_session)):
    try:
        return update_inventory(session, product_id, data)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
