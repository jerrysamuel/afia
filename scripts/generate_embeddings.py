import sys

from app.core.config import settings
from app.db.session import get_engine
from app.infrastructure.search.embeddings import OpenAIEmbeddingProvider
from app.services.embeddings import backfill_product_embeddings
from sqlmodel import Session


def main() -> int:
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    provider = OpenAIEmbeddingProvider(settings.openai_api_key, settings.embedding_model)
    with Session(get_engine()) as session:
        generated, skipped = backfill_product_embeddings(session, provider)
    print(f"generated={generated} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
