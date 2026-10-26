from dataclasses import dataclass

from sqlalchemy import Float, case, or_
from sqlmodel import Session, select

from app.core.config import settings
from app.infrastructure.search.embeddings import EmbeddingProvider
from app.models.embeddings import ProductEmbedding
from app.models.inventory import InventoryItem
from app.models.products import Product, Store


class HybridSearchUnavailableError(RuntimeError):
    """Raised when hybrid retrieval is attempted without PostgreSQL."""


@dataclass(frozen=True)
class HybridProductResult:
    product: Product
    distance: float
    score: float


def search_products_hybrid(
    session: Session,
    query: str,
    provider: EmbeddingProvider,
    *,
    store_slug: str | None = None,
    currency: str | None = None,
    min_amount_minor: int | None = None,
    max_amount_minor: int | None = None,
    available_only: bool = True,
    limit: int | None = None,
) -> list[HybridProductResult]:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        raise HybridSearchUnavailableError("hybrid product search requires PostgreSQL with pgvector")
    if not query.strip():
        return []
    result_limit = settings.semantic_search_limit if limit is None else limit
    if result_limit < 1:
        raise ValueError("hybrid search limit must be greater than zero")

    query_embedding = provider.embed(query)
    if len(query_embedding) != settings.embedding_dimensions:
        raise ValueError(
            f"query embedding provider returned {len(query_embedding)} dimensions; "
            f"expected {settings.embedding_dimensions}"
        )

    distance = ProductEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    keyword_match = case(
        (
            or_(
                Product.name.ilike(f"%{query.strip()}%"),
                Product.description.ilike(f"%{query.strip()}%"),
                Product.category.ilike(f"%{query.strip()}%"),
            ),
            1.0,
        ),
        else_=0.0,
    )
    # Semantic similarity is primary; an exact keyword hit gets a small,
    # deterministic relevance boost without overriding hard commerce filters.
    score = ((1.0 - distance) + (keyword_match * 0.1)).label("score")
    statement = (
        select(Product, distance, score)
        .join(ProductEmbedding, ProductEmbedding.product_id == Product.id)
        .join(Store, Store.id == Product.store_id)
    )
    if available_only:
        statement = statement.join(InventoryItem, InventoryItem.product_id == Product.id).where(
            InventoryItem.available_quantity > 0
        )
    if store_slug:
        statement = statement.where(Store.slug == store_slug)
    if currency:
        statement = statement.where(Product.currency == currency.upper())
    if min_amount_minor is not None:
        statement = statement.where(Product.amount_minor >= min_amount_minor)
    if max_amount_minor is not None:
        statement = statement.where(Product.amount_minor <= max_amount_minor)

    statement = statement.order_by(score.desc(), distance.asc()).limit(result_limit)
    rows = session.exec(statement).all()
    return [HybridProductResult(product=row[0], distance=float(row[1]), score=float(row[2])) for row in rows]
