from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.config import settings
from app.infrastructure.search.embeddings import EmbeddingProvider
from app.models.embeddings import ProductEmbedding
from app.models.products import Product


class SemanticSearchUnavailableError(RuntimeError):
    """Raised when semantic retrieval is attempted without PostgreSQL."""


@dataclass(frozen=True)
class SemanticProductResult:
    product: Product
    distance: float


def search_products_semantically(
    session: Session,
    query: str,
    provider: EmbeddingProvider,
    limit: int | None = None,
) -> list[SemanticProductResult]:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        raise SemanticSearchUnavailableError("semantic product search requires PostgreSQL with pgvector")
    if not query.strip():
        return []
    result_limit = settings.semantic_search_limit if limit is None else limit
    if result_limit < 1:
        raise ValueError("semantic search limit must be greater than zero")

    query_embedding = provider.embed(query)
    if len(query_embedding) != settings.embedding_dimensions:
        raise ValueError(
            f"query embedding provider returned {len(query_embedding)} dimensions; "
            f"expected {settings.embedding_dimensions}"
        )

    distance = ProductEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(Product, distance)
        .join(ProductEmbedding, ProductEmbedding.product_id == Product.id)
        .order_by(distance)
        .limit(result_limit)
    )
    rows = session.exec(statement).all()
    return [SemanticProductResult(product=row[0], distance=float(row[1])) for row in rows]
