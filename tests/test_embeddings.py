import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.v1.endpoints.catalog import post_merchant, post_product, post_store
from app.core.config import settings
from app.models.embeddings import ProductEmbedding
from app.schemas.catalog import MerchantCreate, ProductCreate, StoreCreate
from app.services.embeddings import canonical_product_text, embedding_content_hash, generate_product_embedding


class FakeEmbeddingProvider:
    def __init__(self, dimensions: int = settings.embedding_dimensions):
        self.dimensions = dimensions
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1] * self.dimensions


@pytest.fixture
def product_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        merchant = post_merchant(MerchantCreate(name="Ada", slug="ada"), session)
        post_store(StoreCreate(merchant_id=merchant.id, name="Ada Store", slug="ada-store"), session)
        product = post_product(
            "ada-store",
            ProductCreate(
                name="Oak Table",
                description="Six-seater dining table",
                category="furniture",
                attributes={"material": "solid wood", "seats": 6},
                slug="oak-table",
                amount_minor=100,
                currency="USD",
            ),
            session,
        )
        yield session, product


def test_canonical_text_and_hash_are_deterministic(product_session):
    _, product = product_session
    text = canonical_product_text(product)
    assert text == canonical_product_text(product)
    assert "Six-seater dining table" in text
    assert '"material":"solid wood"' in text
    assert embedding_content_hash(text) == embedding_content_hash(text)


def test_embedding_is_created_and_provider_call_is_skipped_when_fresh(product_session):
    session, product = product_session
    provider = FakeEmbeddingProvider()
    first = generate_product_embedding(session, product.id, provider)
    second = generate_product_embedding(session, product.id, provider)
    assert first.id == second.id
    assert len(provider.calls) == 1
    assert session.exec(select(ProductEmbedding)).all().__len__() == 1


def test_changed_searchable_data_regenerates_embedding(product_session):
    session, product = product_session
    provider = FakeEmbeddingProvider()
    first = generate_product_embedding(session, product.id, provider)
    first_hash = first.content_hash
    product.description = "Eight-seater dining table"
    session.add(product)
    session.commit()
    second = generate_product_embedding(session, product.id, provider)
    assert first.id == second.id
    assert first_hash != second.content_hash
    assert len(provider.calls) == 2


def test_provider_dimension_is_validated(product_session):
    session, product = product_session
    with pytest.raises(ValueError, match="dimensions"):
        generate_product_embedding(session, product.id, FakeEmbeddingProvider(dimensions=3))
    assert session.exec(select(ProductEmbedding)).first() is None
