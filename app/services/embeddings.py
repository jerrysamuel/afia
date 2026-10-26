import hashlib
import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.infrastructure.search.embeddings import EmbeddingProvider
from app.models.embeddings import ProductEmbedding
from app.models.products import Product
from app.services.catalog import CatalogNotFoundError


def canonical_product_text(product: Product) -> str:
    parts = [product.name.strip()]
    if product.description:
        parts.append(product.description.strip())
    if product.category:
        parts.append(f"Category: {product.category.strip()}")
    if product.attributes:
        attributes = json.dumps(product.attributes, sort_keys=True, separators=(",", ":"))
        parts.append(f"Attributes: {attributes}")
    return "\n".join(parts)


def embedding_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_product_embedding(session: Session, product_id: int, provider: EmbeddingProvider) -> ProductEmbedding:
    product = session.get(Product, product_id)
    if product is None:
        raise CatalogNotFoundError("product not found")
    text = canonical_product_text(product)
    content_hash = embedding_content_hash(text)
    existing = session.exec(select(ProductEmbedding).where(ProductEmbedding.product_id == product_id)).first()
    if existing is not None and existing.content_hash == content_hash and existing.model == settings.embedding_model:
        return existing

    vector = provider.embed(text)
    if len(vector) != settings.embedding_dimensions:
        raise ValueError(
            f"embedding provider returned {len(vector)} dimensions; expected {settings.embedding_dimensions}"
        )
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = ProductEmbedding(
            product_id=product_id,
            embedding=vector,
            model=settings.embedding_model,
            content_hash=content_hash,
            created_at=now,
            updated_at=now,
        )
    else:
        existing.embedding = vector
        existing.model = settings.embedding_model
        existing.content_hash = content_hash
        existing.updated_at = now
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def backfill_product_embeddings(session: Session, provider: EmbeddingProvider) -> tuple[int, int]:
    generated = 0
    skipped = 0
    for product in session.exec(select(Product).order_by(Product.id)):
        text = canonical_product_text(product)
        content_hash = embedding_content_hash(text)
        existing = session.exec(select(ProductEmbedding).where(ProductEmbedding.product_id == product.id)).first()
        if existing is not None and existing.content_hash == content_hash and existing.model == settings.embedding_model:
            skipped += 1
            continue
        generate_product_embedding(session, product.id, provider)
        generated += 1
    return generated, skipped
