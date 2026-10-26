from datetime import datetime

from sqlmodel import Field, SQLModel

from app.infrastructure.search.vector_types import EmbeddingVector
from app.models.users import utc_now


class ProductEmbedding(SQLModel, table=True):
    __tablename__ = "product_embeddings"

    id: int | None = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id", unique=True, index=True)
    embedding: list[float] = Field(sa_type=EmbeddingVector())
    model: str = Field(max_length=100)
    content_hash: str = Field(max_length=64, index=True)
    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now, nullable=False)
