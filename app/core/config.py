import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    database_url: str = os.getenv("DATABASE_URL")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    semantic_search_limit: int = int(os.getenv("SEMANTIC_SEARCH_LIMIT", "20"))
    x402_api_key: str | None = os.getenv("X402_API_KEY")
    x402_facilitator_url: str = os.getenv("X402_FACILITATOR_URL", "https://api.x402.sepolia.celo.org")
    x402_network: str = os.getenv("X402_NETWORK", "eip155:11142220")
    # Celo Sepolia USDC is the safe default for local/testnet work. Production
    # environments must override this with their explicitly approved asset.
    x402_asset: str | None = os.getenv(
        "X402_ASSET",
        "0x01C5C0122039549AD1493B8220cABEdD739BC44E",
    )
    x402_asset_name: str = os.getenv("X402_ASSET_NAME", "USDC")
    x402_asset_version: str = os.getenv("X402_ASSET_VERSION", "2")
    x402_pay_to: str | None = os.getenv("X402_PAY_TO")
    x402_max_timeout_seconds: int = int(os.getenv("X402_MAX_TIMEOUT_SECONDS", "300"))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    )


settings = Settings()
