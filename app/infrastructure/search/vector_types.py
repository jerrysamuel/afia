from sqlalchemy import JSON, Float, TypeDecorator

from app.core.config import settings


class EmbeddingVector(TypeDecorator):
    """pgvector on PostgreSQL; JSON only for SQLite unit tests/local fallback."""

    impl = JSON
    cache_ok = True

    class comparator_factory(TypeDecorator.Comparator):
        def cosine_distance(self, other):
            return self.expr.op("<=>", return_type=Float)(other)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(settings.embedding_dimensions))
        return dialect.type_descriptor(JSON())
