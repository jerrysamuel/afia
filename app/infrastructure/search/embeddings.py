from typing import Protocol

from app.core.config import settings


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float]:
        ...


class EmbeddingProviderError(RuntimeError):
    """Raised when the configured hosted embedding provider is unavailable."""


class OpenAIEmbeddingProvider:
    """OpenAI adapter; application services depend only on EmbeddingProvider."""

    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model = model

    def embed(self, text: str) -> list[float]:
        try:
            response = self._client.embeddings.create(
                input=text.replace("\n", " "),
                model=self.model,
            )
        except Exception as exc:
            raise EmbeddingProviderError("hosted embedding provider request failed") from exc
        return response.data[0].embedding


def get_configured_embedding_provider() -> EmbeddingProvider | None:
    if not settings.openai_api_key:
        return None
    return OpenAIEmbeddingProvider(settings.openai_api_key, settings.embedding_model)
