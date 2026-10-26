"""Add product embedding persistence and searchable product metadata."""
from alembic import op
import sqlalchemy as sa

from app.core.config import settings

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - migrations require pgvector in deployments
    Vector = None

revision = "0006_product_embeddings"
down_revision = "0005_carts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("products", sa.Column("attributes", sa.JSON(), nullable=False, server_default="{}"))
    op.create_index("ix_products_category", "products", ["category"], unique=False)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        if Vector is None:
            raise RuntimeError("pgvector is required for PostgreSQL migrations")
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        embedding_type = Vector(settings.embedding_dimensions)
    else:
        # SQLite is used for unit tests/local fallback; it does not emulate
        # pgvector and is never used for vector similarity queries.
        embedding_type = sa.JSON()

    op.create_table(
        "product_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )
    op.create_index("ix_product_embeddings_product_id", "product_embeddings", ["product_id"], unique=False)
    op.create_index("ix_product_embeddings_content_hash", "product_embeddings", ["content_hash"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_embeddings_content_hash", table_name="product_embeddings")
    op.drop_index("ix_product_embeddings_product_id", table_name="product_embeddings")
    op.drop_table("product_embeddings")
    op.drop_index("ix_products_category", table_name="products")
    op.drop_column("products", "attributes")
    op.drop_column("products", "category")
