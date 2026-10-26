from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.products import Product
from app.services.semantic_search import SemanticSearchUnavailableError, search_products_semantically


class FakeProvider:
    def __init__(self):
        self.queries: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1] * settings.embedding_dimensions


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def get_bind(self):
        return self.bind

    def exec(self, statement):
        self.statement = statement
        return FakeResult(self.rows)


def product(product_id: int) -> Product:
    return Product(id=product_id, store_id=1, name=f"Product {product_id}", amount_minor=100, currency="USD")


def test_query_embedding_uses_provider_and_returns_distance_in_order():
    rows = [(product(2), 0.12), (product(1), 0.31)]
    session = FakeSession(rows)
    provider = FakeProvider()
    results = search_products_semantically(session, "family dining furniture", provider, limit=2)
    assert provider.queries == ["family dining furniture"]
    assert [result.product.id for result in results] == [2, 1]
    assert [result.distance for result in results] == [0.12, 0.31]
    assert "<=>" in str(session.statement)


def test_result_limit_is_applied_to_query():
    session = FakeSession([])
    search_products_semantically(session, "table", FakeProvider(), limit=7)
    assert session.statement._limit_clause.value == 7


def test_default_limit_is_configured():
    session = FakeSession([])
    search_products_semantically(session, "table", FakeProvider())
    assert session.statement._limit_clause.value == settings.semantic_search_limit


def test_sqlite_search_is_rejected_without_attempting_vector_retrieval():
    session = FakeSession([])
    session.bind.dialect.name = "sqlite"
    provider = FakeProvider()
    with pytest.raises(SemanticSearchUnavailableError):
        search_products_semantically(session, "table", provider)
    assert provider.queries == []


def test_wrong_query_embedding_dimension_is_rejected():
    class WrongDimensionProvider:
        def embed(self, text: str):
            return [0.1]

    with pytest.raises(ValueError, match="dimensions"):
        search_products_semantically(FakeSession([]), "table", WrongDimensionProvider())
