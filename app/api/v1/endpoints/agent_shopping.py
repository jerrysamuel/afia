from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.api.deps import get_x402_provider
from app.db.session import get_session
from app.infrastructure.search.embeddings import EmbeddingProviderError, get_configured_embedding_provider
from app.infrastructure.x402 import X402PaymentProvider
from app.schemas.catalog import InventoryRead, ProductRead
from app.schemas.orders import OrderCreate, OrderRead
from app.schemas.payments import (
    PaymentAttemptCreate,
    PaymentCreate,
    PaymentRead,
    X402AttemptResultRead,
    X402PayloadSubmit,
)
from app.services.catalog import CatalogConflictError, CatalogNotFoundError, get_inventory, get_product, search_products
from app.services.hybrid_search import HybridSearchUnavailableError, search_products_hybrid
from app.services.orders import create_order, get_order
from app.services.payments import (
    PaymentStateError,
    create_payment,
    expire_payment,
    get_payment,
    process_x402_attempt,
    start_attempt,
)

router = APIRouter(prefix="/api/v1/agent/shopping", tags=["agent-shopping"])


@router.get("/products/search", response_model=list[ProductRead])
def shopping_search(
    query: str | None = Query(default=None, max_length=200),
    store_slug: str | None = None,
    currency: str | None = None,
    min_amount_minor: int | None = Query(default=None, ge=0),
    max_amount_minor: int | None = Query(default=None, ge=0),
    available_only: bool = True,
    session: Session = Depends(get_session),
):
    try:
        provider = get_configured_embedding_provider()
        if provider is not None and query and query.strip():
            try:
                hybrid_results = search_products_hybrid(
                    session,
                    query or "",
                    provider,
                    store_slug=store_slug,
                    currency=currency,
                    min_amount_minor=min_amount_minor,
                    max_amount_minor=max_amount_minor,
                    available_only=available_only,
                )
                return [result.product for result in hybrid_results]
            except (EmbeddingProviderError, HybridSearchUnavailableError):
                pass
        return search_products(session, query, store_slug, currency, min_amount_minor, max_amount_minor, available_only)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/products/{product_id}", response_model=ProductRead)
def shopping_product(product_id: int, session: Session = Depends(get_session)):
    try:
        return get_product(session, product_id)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/products/{product_id}/availability", response_model=InventoryRead)
def shopping_availability(product_id: int, session: Session = Depends(get_session)):
    try:
        return get_inventory(session, product_id)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def shopping_create_order(data: OrderCreate, session: Session = Depends(get_session)):
    try:
        order = create_order(session, data)
        _, items = get_order(session, order.id)
        return OrderRead.model_validate({**order.model_dump(), "items": items})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/orders/{order_id}", response_model=OrderRead)
def shopping_get_order(order_id: int, session: Session = Depends(get_session)):
    try:
        order, items = get_order(session, order_id)
        return OrderRead.model_validate({**order.model_dump(), "items": items})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/orders/{order_id}/payment", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def shopping_create_payment(order_id: int, data: PaymentCreate, session: Session = Depends(get_session)):
    try:
        payment = create_payment(session, order_id, data.provider)
        payment_record, attempts = get_payment(session, payment.id)
        return PaymentRead.model_validate({**payment_record.model_dump(), "attempts": attempts})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/payments/{payment_id}/attempts", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def shopping_create_payment_attempt(
    payment_id: int,
    data: PaymentAttemptCreate,
    session: Session = Depends(get_session),
):
    try:
        start_attempt(session, payment_id, data.provider)
        payment, attempts = get_payment(session, payment_id)
        return PaymentRead.model_validate({**payment.model_dump(), "attempts": attempts})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaymentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/payments/{payment_id}", response_model=PaymentRead)
def shopping_get_payment(payment_id: int, session: Session = Depends(get_session)):
    try:
        payment, attempts = get_payment(session, payment_id)
        return PaymentRead.model_validate({**payment.model_dump(), "attempts": attempts})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/payments/{payment_id}/expire", response_model=PaymentRead)
def shopping_expire_payment(payment_id: int, session: Session = Depends(get_session)):
    try:
        expire_payment(session, payment_id)
        payment, attempts = get_payment(session, payment_id)
        return PaymentRead.model_validate({**payment.model_dump(), "attempts": attempts})
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaymentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/payments/{payment_id}/attempts/{attempt_id}/x402",
    response_model=X402AttemptResultRead,
    status_code=status.HTTP_200_OK,
    summary="Submit a signed x402 payment payload (agent shopping)",
)
async def shopping_post_x402_attempt(
    payment_id: int,
    attempt_id: int,
    body: X402PayloadSubmit,
    session: Session = Depends(get_session),
    provider: X402PaymentProvider = Depends(get_x402_provider),
):
    """Verify and settle one x402 payment attempt on Celo (agent shopping path).

    Call this after ``POST /payments/{id}/attempts`` to submit the wallet-signed
    PaymentPayload.  On success the order is marked SETTLED and the on-chain
    transaction hash is returned.

    **State transitions triggered (on success):**
    - PaymentAttempt: PROCESSING → VERIFIED → SETTLED
    - Payment:        PROCESSING → VERIFIED → SETTLED
    - Order: PENDING_PAYMENT/CREATED → CONFIRMED/SETTLED
    """
    try:
        result = await process_x402_attempt(
            session, attempt_id, body.payload, provider, payment_id=payment_id
        )
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaymentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    settled = result.attempt.status == "SETTLED"
    invalid_reason = (
        result.verification.invalid_reason
        if result.verification and not result.verification.is_valid
        else None
    )
    error_reason = (
        result.settlement.error_reason
        if result.settlement and not result.settlement.success
        else None
    )

    payment_data = (
        result.payment.model_dump()
        if hasattr(result.payment, "model_dump")
        else result.payment.__dict__
    )
    attempt_read = (
        result.attempt.model_dump()
        if hasattr(result.attempt, "model_dump")
        else result.attempt.__dict__
    )

    return X402AttemptResultRead(
        success=settled,
        transaction=result.settlement.transaction if result.settlement else None,
        payer=(
            result.settlement.payer
            if result.settlement
            else (result.verification.payer if result.verification else None)
        ),
        network=result.settlement.network if result.settlement else None,
        error_reason=error_reason,
        invalid_reason=invalid_reason,
        attempt=attempt_read,
        payment={**payment_data, "attempts": [result.attempt]},
    )
