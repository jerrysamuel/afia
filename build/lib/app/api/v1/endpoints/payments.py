from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import get_x402_provider
from app.db.session import get_session
from app.infrastructure.x402 import X402PaymentProvider
from app.schemas.payments import (
    PaymentAttemptCreate,
    PaymentCreate,
    PaymentRead,
    X402AttemptResultRead,
    X402PayloadSubmit,
)
from app.services.catalog import CatalogConflictError, CatalogNotFoundError
from app.services.payments import (
    PaymentStateError,
    create_payment,
    expire_payment,
    get_payment,
    process_x402_attempt,
    start_attempt,
)

router = APIRouter(prefix="/api/v1", tags=["payments"])


def _read_payment(session: Session, payment_id: int) -> PaymentRead:
    payment, attempts = get_payment(session, payment_id)
    return PaymentRead.model_validate({**payment.model_dump(), "attempts": attempts})


@router.post("/orders/{order_id}/payment", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def post_payment(order_id: int, data: PaymentCreate, session: Session = Depends(get_session)):
    try:
        payment = create_payment(session, order_id, data.provider)
        return _read_payment(session, payment.id)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CatalogConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/payments/{payment_id}/attempts", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def post_payment_attempt(payment_id: int, data: PaymentAttemptCreate, session: Session = Depends(get_session)):
    try:
        start_attempt(session, payment_id, data.provider)
        return _read_payment(session, payment_id)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaymentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/payments/{payment_id}", response_model=PaymentRead)
def get_payment_endpoint(payment_id: int, session: Session = Depends(get_session)):
    try:
        return _read_payment(session, payment_id)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/payments/{payment_id}/expire", response_model=PaymentRead)
def expire_payment_endpoint(payment_id: int, session: Session = Depends(get_session)):
    try:
        expire_payment(session, payment_id)
        return _read_payment(session, payment_id)
    except CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaymentStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/payments/{payment_id}/attempts/{attempt_id}/x402",
    response_model=X402AttemptResultRead,
    tags=["payments"],
    summary="Submit a signed x402 payment payload",
)
async def post_x402_attempt(
    payment_id: int,
    attempt_id: int,
    body: X402PayloadSubmit,
    session: Session = Depends(get_session),
    provider: X402PaymentProvider = Depends(get_x402_provider),
):
    """Verify and settle one x402 payment attempt on Celo.

    The client (agent) should call this endpoint after receiving a 402
    response from a protected resource.  ``body.payload`` must be the
    decoded PaymentPayload dict that the agent constructed from its wallet
    signature.

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

    # Determine overall success and surface the right error field
    settled = result.attempt.status == "SETTLED"
    invalid_reason = result.verification.invalid_reason if result.verification and not result.verification.is_valid else None
    error_reason = result.settlement.error_reason if result.settlement and not result.settlement.success else None

    attempt_read = (
        result.attempt.model_dump()
        if hasattr(result.attempt, "model_dump")
        else result.attempt.__dict__
    )
    payment_data = (
        result.payment.model_dump()
        if hasattr(result.payment, "model_dump")
        else result.payment.__dict__
    )
    payment_read = {**payment_data, "attempts": [result.attempt]}

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
        payment=payment_read,
    )
