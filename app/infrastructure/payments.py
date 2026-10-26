from dataclasses import dataclass
from typing import Any, Protocol

from app.models.payments import Payment, PaymentAttempt


@dataclass(frozen=True)
class ProviderAttemptResult:
    """Provider output needed by Afia after a provider integration is added."""

    provider_reference: str | None = None


class PaymentProvider(Protocol):
    """Boundary for a future provider adapter.

    The provider may start processing an attempt, but Afia's payment service
    remains responsible for recording and validating state transitions.
    """

    name: str

    def start_attempt(self, payment: Payment, attempt: PaymentAttempt) -> ProviderAttemptResult:
        ...
