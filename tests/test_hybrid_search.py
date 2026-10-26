from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.products import Product
from app.services.hybrid_search import HybridSearchUnavailableError, search_products_hybrid


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


def product(product_id: int, currency: str = "USD", amount: int = 100) -> Product:
    return Product(id=product_id, store_id=1, name=f"Product {product_id}", amount_minor=amount, currency=currency)


def test_hybrid_search_uses_provider_and_returns_ranked_scores():
    rows = [(product(2), 0.08, 1.02), (product(1), 0.24, 0.76)]
    session = FakeSession(rows)
    provider = FakeProvider()
    results = search_products_hybrid(
        session,
        "family dining table",
        provider,
        store_slug="ada-furniture",
        currency="usd",
        min_amount_minor=10,
        max_amount_minor=50000,
        available_only=True,
        limit=2,
    )
    assert provider.queries == ["family dining table"]
    assert [result.product.id for result in results] == [2, 1]
    assert [result.distance for result in results] == [0.08, 0.24]
    assert [result.score for result in results] == [1.02, 0.76]
    sql = str(session.statement)
    assert "<=>" in sql
    assert "available_quantity" in sql
    assert "amount_minor" in sql
    assert "currency" in sql
    assert session.statement._limit_clause.value == 2


def test_hybrid_search_default_limit_is_configured():
    session = FakeSession([])
    search_products_hybrid(session, "table", FakeProvider())
    assert session.statement._limit_clause.value == settings.semantic_search_limit


def test_hybrid_search_rejects_sqlite_without_calling_provider():
    session = FakeSession([])
    session.bind.dialect.name = "sqlite"
    provider = FakeProvider()
    with pytest.raises(HybridSearchUnavailableError):
        search_products_hybrid(session, "table", provider)
    assert provider.queries == []


def test_hybrid_search_validates_query_embedding_dimension():
    class WrongDimensionProvider:
        def embed(self, text: str):
            return [0.1]

    with pytest.raises(ValueError, match="dimensions"):
        search_products_hybrid(FakeSession([]), "table", WrongDimensionProvider())
