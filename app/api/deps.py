from functools import lru_cache

from fastapi import Header, HTTPException, status, Depends
from sqlmodel import Session

from app.db.session import get_session
from app.models.users import Customer
from app.services.auth import customer_id_from_token

from app.infrastructure.x402 import X402PaymentProvider, X402PaymentProviderError


@lru_cache(maxsize=1)
def _build_x402_provider() -> X402PaymentProvider:
    """Build and cache the X402PaymentProvider singleton.

    Raises X402PaymentProviderError if required settings are missing.
    Cached so the facilitator HTTP client is reused across requests.
    """
    return X402PaymentProvider()


def get_x402_provider() -> X402PaymentProvider:
    """FastAPI dependency that resolves the x402 payment provider.

    Returns the cached provider or raises HTTP 503 if the provider is
    misconfigured (e.g. X402_ASSET or X402_PAY_TO not set in .env).
    """
    try:
        return _build_x402_provider()
    except X402PaymentProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"x402 payment provider not configured: {exc}",
        ) from exc


def get_current_customer(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Customer:
    """Require a valid customer bearer token for shopper-owned resources."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    customer_id = customer_id_from_token(authorization[7:].strip())
    customer = session.get(Customer, customer_id) if customer_id else None
    if customer is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")
    return customer
