import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str | None = os.getenv("DATABASE_URL")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    semantic_search_limit: int = int(os.getenv("SEMANTIC_SEARCH_LIMIT", "20"))
    x402_api_key: str | None = os.getenv("X402_API_KEY")
    x402_facilitator_url: str = os.getenv("X402_FACILITATOR_URL", "https://api.x402.celo.org")
    x402_network: str = os.getenv("X402_NETWORK", "eip155:42220")
    # USA₮ on Celo mainnet. Override all x402_* values for local/testnet work.
    x402_asset: str | None = os.getenv(
        "X402_ASSET",
        "0xD2ab3C9A02DBBAB236BfEC45D1d755DF4267F771",
    )
    x402_asset_name: str = os.getenv("X402_ASSET_NAME", "Tether America USD")
    x402_asset_version: str = os.getenv("X402_ASSET_VERSION", "1")
    x402_pay_to: str | None = os.getenv("X402_PAY_TO")
    x402_max_timeout_seconds: int = int(os.getenv("X402_MAX_TIMEOUT_SECONDS", "300"))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    )
    auth_secret: str = os.getenv("AUTH_SECRET", "change-this-auth-secret-before-production")


settings = Settings()


def validate_production_settings() -> None:
    """Fail fast instead of starting a partially configured payment service."""
    if settings.app_env != "production":
        return
    required = {
        "DATABASE_URL": settings.database_url,
        "CORS_ORIGINS": settings.cors_origins,
        "AUTH_SECRET": settings.auth_secret,
        "X402_API_KEY": settings.x402_api_key,
        "X402_ASSET": settings.x402_asset,
    }
    missing = [name for name, value in required.items() if not value or value == "change-this-auth-secret-before-production"]
    if missing:
        raise RuntimeError(f"Missing production configuration: {', '.join(missing)}")
    if settings.x402_network != "eip155:42220":
        raise RuntimeError("Production x402 network must be Celo mainnet eip155:42220")
