from functools import lru_cache

from fastapi import HTTPException, status

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
