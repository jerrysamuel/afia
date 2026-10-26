from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import settings
from app.infrastructure.payments import ProviderAttemptResult
from app.models.payments import Payment, PaymentAttempt, PaymentAttemptStatus


class X402PaymentProviderError(RuntimeError):
    """A provider/configuration error; no Afia payment state is changed."""


class FacilitatorClient(Protocol):
    async def verify(self, payload: Any, requirements: Any) -> Any:
        ...

    async def settle(self, payload: Any, requirements: Any) -> Any:
        ...


@dataclass(frozen=True)
class X402VerificationResult:
    is_valid: bool
    payer: str | None = None
    invalid_reason: str | None = None


@dataclass(frozen=True)
class X402SettlementResult:
    success: bool
    transaction: str | None = None
    payer: str | None = None
    error_reason: str | None = None
    network: str | None = None


class X402PaymentProvider:
    """Celo x402 adapter; blockchain-specific behavior stays here.

    The adapter intentionally does not mutate Afia models. The application
    service remains responsible for applying VERIFIED/SETTLED transitions.
    """

    name = "x402"

    def __init__(
        self,
        facilitator: FacilitatorClient | None = None,
        *,
        network: str | None = None,
        asset: str | None = None,
        pay_to: str | None = None,
        max_timeout_seconds: int | None = None,
        currency_minor_digits: int = 2,
        asset_decimals: int = 6,
        asset_name: str | None = None,
        asset_version: str | None = None,
    ) -> None:
        if facilitator is None:
            from x402.http import (
                CreateHeadersAuthProvider,
             FacilitatorConfig,
                HTTPFacilitatorClient,
            )

            api_key = settings.x402_api_key
            if not api_key:
                raise X402PaymentProviderError(
                    "X402_API_KEY is required — get one at https://x402.celo.org"
                )

            def _make_auth_headers() -> dict[str, dict[str, str]]:
                h = {"X-API-Key": api_key}
                return {"verify": h, "settle": h, "supported": h}

            facilitator = HTTPFacilitatorClient(
                FacilitatorConfig(
                    url=settings.x402_facilitator_url,
                    auth_provider=CreateHeadersAuthProvider(_make_auth_headers),
                )
            )
        self.facilitator = facilitator
        self.network = network or settings.x402_network
        self.asset = asset or settings.x402_asset
        self.pay_to = pay_to or settings.x402_pay_to
        self.max_timeout_seconds = max_timeout_seconds or settings.x402_max_timeout_seconds
        self.currency_minor_digits = currency_minor_digits
        self.asset_decimals = asset_decimals
        self.asset_name = asset_name or settings.x402_asset_name
        self.asset_version = asset_version or settings.x402_asset_version
        if self.network not in {"eip155:42220", "eip155:11142220"}:
            raise X402PaymentProviderError("unsupported Celo x402 network")
        if not self.asset or not self.pay_to:
            raise X402PaymentProviderError("X402_ASSET and X402_PAY_TO must be configured")

    def start_attempt(self, payment: Payment, attempt: PaymentAttempt) -> ProviderAttemptResult:
        """Satisfy the traditional provider boundary without simulating payment."""
        if attempt.status != PaymentAttemptStatus.PROCESSING:
            raise X402PaymentProviderError("x402 attempts must be processing before a payload is verified")
        return ProviderAttemptResult()

    def build_requirements(self, payment: Payment):
        from x402.schemas import PaymentRequirements

        if payment.currency.upper() != "USD":
            raise X402PaymentProviderError("Celo x402 adapter currently requires USD orders")
        if payment.amount_minor < 0:
            raise X402PaymentProviderError("payment amount cannot be negative")
        atomic_amount = payment.amount_minor * 10 ** (self.asset_decimals - self.currency_minor_digits)
        return PaymentRequirements(
            scheme="exact",
            network=self.network,
            asset=self.asset,
            amount=str(atomic_amount),
            payTo=self.pay_to,
            maxTimeoutSeconds=self.max_timeout_seconds,
            extra={"name": self.asset_name, "version": self.asset_version},
        )

    def _parse_payload(self, raw_payload: dict[str, Any]):
        from x402.schemas import PaymentPayload

        try:
            return PaymentPayload.model_validate(raw_payload)
        except Exception as exc:
            raise X402PaymentProviderError("invalid x402 payment payload") from exc

    async def verify(self, payment: Payment, raw_payload: dict[str, Any]) -> X402VerificationResult:
        payload = self._parse_payload(raw_payload)
        requirements = self.build_requirements(payment)
        accepted = payload.accepted
        if (
            accepted.network != requirements.network
            or accepted.asset != requirements.asset
            or accepted.amount != requirements.amount
            or accepted.pay_to != requirements.pay_to
        ):
            return X402VerificationResult(False, invalid_reason="payment requirements do not match order")
        response = await self.facilitator.verify(payload, requirements)
        return X402VerificationResult(
            is_valid=bool(response.is_valid),
            payer=response.payer,
            invalid_reason=response.invalid_reason,
        )

    async def settle(self, payment: Payment, raw_payload: dict[str, Any]) -> X402SettlementResult:
        payload = self._parse_payload(raw_payload)
        requirements = self.build_requirements(payment)
        response = await self.facilitator.settle(payload, requirements)
        return X402SettlementResult(
            success=bool(response.success),
            transaction=response.transaction or None,
            payer=response.payer,
            error_reason=response.error_reason,
            network=response.network,
        )
