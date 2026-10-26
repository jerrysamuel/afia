from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlmodel import Session, select

from app.models.orders import Order
from app.models.payments import (
    PAYMENT_ATTEMPT_TRANSITIONS,
    PAYMENT_TRANSITIONS,
    Payment,
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentStatus,
)
from app.infrastructure.x402 import X402PaymentProvider, X402SettlementResult, X402VerificationResult
from app.services.catalog import CatalogConflictError, CatalogNotFoundError
from app.services.orders import release_order_reservation


class PaymentStateError(Exception):
    pass


@dataclass(frozen=True)
class X402AttemptProcessingResult:
    verification: X402VerificationResult | None
    settlement: X402SettlementResult | None
    attempt: PaymentAttempt
    payment: Payment


def _now():
    return datetime.now(timezone.utc)


def create_payment(session: Session, order_id: int, provider: str) -> Payment:
    existing = session.exec(select(Payment).where(Payment.order_id == order_id)).first()
    if existing is not None:
        return existing
    order = session.get(Order, order_id)
    if order is None:
        raise CatalogNotFoundError("order not found")
    payment = Payment(
        order_id=order.id,
        amount_minor=order.total_amount_minor,
        currency=order.currency,
        provider=provider,
    )
    session.add(payment)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        existing = session.exec(select(Payment).where(Payment.order_id == order_id)).first()
        if existing is not None:
            return existing
        raise CatalogConflictError("payment could not be created") from exc
    session.refresh(payment)
    return payment


def start_attempt(session: Session, payment_id: int, provider: str | None = None) -> PaymentAttempt:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise CatalogNotFoundError("payment not found")
    if payment.status not in {PaymentStatus.CREATED, PaymentStatus.FAILED}:
        raise PaymentStateError(f"cannot start an attempt for payment in {payment.status} state")
    existing_attempts = list(session.exec(select(PaymentAttempt).where(PaymentAttempt.payment_id == payment_id)))
    attempt_number = len(existing_attempts) + 1
    attempt = PaymentAttempt(
        payment_id=payment_id,
        attempt_number=attempt_number,
        provider=provider or payment.provider,
        status=PaymentAttemptStatus.PROCESSING,
    )
    payment.status = PaymentStatus.PROCESSING
    payment.updated_at = _now()
    session.add(attempt)
    session.add(payment)
    session.commit()
    session.refresh(attempt)
    return attempt


def transition_payment(session: Session, payment_id: int, new_status: PaymentStatus) -> Payment:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise CatalogNotFoundError("payment not found")
    current = PaymentStatus(payment.status)
    if new_status not in PAYMENT_TRANSITIONS[current]:
        raise PaymentStateError(f"invalid payment transition: {current} -> {new_status}")
    payment.status = new_status
    payment.updated_at = _now()
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


def transition_attempt(session: Session, attempt_id: int, new_status: PaymentAttemptStatus) -> PaymentAttempt:
    attempt = session.get(PaymentAttempt, attempt_id)
    if attempt is None:
        raise CatalogNotFoundError("payment attempt not found")
    current = PaymentAttemptStatus(attempt.status)
    if new_status not in PAYMENT_ATTEMPT_TRANSITIONS[current]:
        raise PaymentStateError(f"invalid payment attempt transition: {current} -> {new_status}")
    attempt.status = new_status
    attempt.updated_at = _now()
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def get_payment(session: Session, payment_id: int) -> tuple[Payment, list[PaymentAttempt]]:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise CatalogNotFoundError("payment not found")
    attempts = list(session.exec(select(PaymentAttempt).where(PaymentAttempt.payment_id == payment.id).order_by(PaymentAttempt.attempt_number)))
    return payment, attempts


async def process_x402_attempt(
    session: Session,
    attempt_id: int,
    payment_payload: dict[str, Any],
    provider: X402PaymentProvider,
    *,
    payment_id: int | None = None,
) -> X402AttemptProcessingResult:
    """Process one attempt with a cross-worker lock on PostgreSQL."""
    is_postgres = session.bind is not None and session.bind.dialect.name == "postgresql"
    previous_expire_on_commit = session.expire_on_commit
    if is_postgres:
        # Keep the result models readable after the lock cleanup commits.
        session.expire_on_commit = False
    if is_postgres:
        session.exec(text("SELECT pg_advisory_lock(:attempt_id)").bindparams(attempt_id=attempt_id))
    try:
        return await _process_x402_attempt(
            session,
            attempt_id,
            payment_payload,
            provider,
            payment_id=payment_id,
        )
    except Exception:
        if is_postgres:
            session.rollback()
        raise
    finally:
        if is_postgres:
            # The lock is session-scoped, so release it after all state commits.
            session.exec(text("SELECT pg_advisory_unlock(:attempt_id)").bindparams(attempt_id=attempt_id))
            session.commit()
            session.expire_on_commit = previous_expire_on_commit


async def _process_x402_attempt(
    session: Session,
    attempt_id: int,
    payment_payload: dict[str, Any],
    provider: X402PaymentProvider,
    *,
    payment_id: int | None = None,
) -> X402AttemptProcessingResult:
    """Verify and settle one existing x402 attempt, safely resumable on retry."""
    attempt = session.get(PaymentAttempt, attempt_id)
    if attempt is None:
        raise CatalogNotFoundError("payment attempt not found")
    payment = session.get(Payment, attempt.payment_id)
    if payment is None:
        raise CatalogNotFoundError("payment not found")
    if payment_id is not None and payment.id != payment_id:
        raise PaymentStateError("payment attempt does not belong to payment")

    if attempt.status == PaymentAttemptStatus.SETTLED:
        return X402AttemptProcessingResult(None, None, attempt, payment)

    verification: X402VerificationResult | None = None
    if attempt.status == PaymentAttemptStatus.PROCESSING:
        verification = await provider.verify(payment, payment_payload)
        if not verification.is_valid:
            attempt.failure_code = verification.invalid_reason
            attempt.failure_message = verification.invalid_reason
            session.add(attempt)
            session.commit()
            transition_attempt(session, attempt.id, PaymentAttemptStatus.FAILED)
            transition_payment(session, payment.id, PaymentStatus.FAILED)
            session.refresh(attempt)
            session.refresh(payment)
            return X402AttemptProcessingResult(verification, None, attempt, payment)
        transition_attempt(session, attempt.id, PaymentAttemptStatus.VERIFIED)
        transition_payment(session, payment.id, PaymentStatus.VERIFIED)
        session.refresh(attempt)
        session.refresh(payment)

    settlement = await provider.settle(payment, payment_payload)
    if settlement.success:
        attempt.provider_reference = settlement.transaction
        session.add(attempt)
        session.commit()
        transition_attempt(session, attempt.id, PaymentAttemptStatus.SETTLED)
        transition_payment(session, payment.id, PaymentStatus.SETTLED)
        order = session.get(Order, payment.order_id)
        if order is not None:
            order.payment_status = PaymentStatus.SETTLED.value
            order.status = "CONFIRMED"
            order.updated_at = _now()
            session.add(order)
            session.commit()
        session.refresh(attempt)
        session.refresh(payment)
    elif settlement.error_reason:
        attempt.failure_code = "settlement_failed"
        attempt.failure_message = settlement.error_reason
        session.add(attempt)
        session.commit()
        session.refresh(attempt)
        session.refresh(payment)
    return X402AttemptProcessingResult(verification, settlement, attempt, payment)


def expire_payment(session: Session, payment_id: int) -> Payment:
    """Expire an unpaid payment and release its order reservation.

    Verified payments are deliberately not expired: they may already be in
    the facilitator's settlement path and must be reconciled instead.
    """
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise CatalogNotFoundError("payment not found")
    if payment.status in {PaymentStatus.SETTLED, PaymentStatus.EXPIRED}:
        return payment
    if payment.status == PaymentStatus.VERIFIED:
        raise PaymentStateError("verified payments must be settled or reconciled")

    attempts = list(
        session.exec(select(PaymentAttempt).where(PaymentAttempt.payment_id == payment.id))
    )
    for attempt in attempts:
        if attempt.status in {PaymentAttemptStatus.PROCESSING, PaymentAttemptStatus.CREATED}:
            attempt.status = PaymentAttemptStatus.EXPIRED
            attempt.updated_at = _now()
            session.add(attempt)
    payment.status = PaymentStatus.EXPIRED
    payment.updated_at = _now()
    session.add(payment)
    order = session.get(Order, payment.order_id)
    if order is not None:
        release_order_reservation(session, order.id)
        order.status = "CANCELLED"
        order.payment_status = PaymentStatus.EXPIRED.value
        order.updated_at = _now()
        session.add(order)
    session.commit()
    session.refresh(payment)
    return payment
