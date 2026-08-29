"""Embedding-provider selection for conversational memory."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Provides validated local semantic embeddings for conversation recall.

from __future__ import annotations

import math
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests  # type: ignore[import-untyped]

from model.plugin_routing.embeddings import EmbeddingProvider
from model.plugin_routing.embeddings import HashEmbeddingProvider


class OllamaConversationEmbeddingProvider(EmbeddingProvider):
    """Generate semantic embeddings through Ollama's structured embed API."""

    def __init__(
        self,
        *,
        service_url: str,
        model_id: str,
        dimensions: int,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 30.0,
    ) -> None:
        """Initialise one pinned local embedding profile."""
        parsed = urlparse(str(service_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("conversation embedding service URL must be HTTP(S)")
        model = str(model_id or "").strip()
        if not model:
            raise ValueError("conversation embedding model id is required")
        if dimensions <= 0:
            raise ValueError("conversation embedding dimensions must be positive")
        base_path = parsed.path.rstrip("/")
        self._endpoint = urlunparse(
            parsed._replace(path=f"{base_path}/api/embed", params="", query="", fragment="")
        )
        self._model_id = model
        self._dimensions = int(dimensions)
        self._timeout = (
            max(0.1, float(connect_timeout_seconds)),
            max(0.1, float(read_timeout_seconds)),
        )

    @property
    def model_id(self) -> str:
        """Return the exact configured embedding model identifier."""
        return self._model_id

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return finite, dimension-checked embeddings for every input text."""
        if not texts:
            return []
        inputs = [str(item or "").strip() for item in texts]
        if any(not item for item in inputs):
            raise ValueError("conversation embedding input must not be empty")
        response = requests.post(
            self._endpoint,
            json={"model": self._model_id, "input": inputs},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        vectors = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(vectors, list) or len(vectors) != len(inputs):
            raise ValueError("conversation embedding response count is invalid")

        validated: list[list[float]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != self._dimensions:
                raise ValueError("conversation embedding dimensions are invalid")
            values = [float(item) for item in vector]
            if any(not math.isfinite(item) for item in values):
                raise ValueError("conversation embedding contains non-finite values")
            validated.append(values)
        return validated


def conversation_embedding_provider(config_mgr: Any | None) -> EmbeddingProvider:
    """Build the configured conversational-memory embedding provider."""
    provider_code = _config_value(config_mgr, "embedding_provider", "hash").lower()
    model_id = _config_value(config_mgr, "embedding_model_id", "hash-embedding-v1")
    dimensions = _config_int(config_mgr, "embedding_dimensions", 32)
    if provider_code == "hash":
        return HashEmbeddingProvider(model_id=model_id, dimensions=dimensions)
    if provider_code == "ollama":
        service_url = _config_value(config_mgr, "embedding_service_url", "")
        return OllamaConversationEmbeddingProvider(
            service_url=service_url,
            model_id=model_id,
            dimensions=dimensions,
        )
    raise ValueError(
        f"unsupported conversation embedding provider '{provider_code}'"
    )


def _config_value(config_mgr: Any | None, key: str, default: str) -> str:
    """Read one conversational-memory string setting."""
    if config_mgr is None:
        return default
    return str(config_mgr.config_value("conversation_memory", key, default=default)).strip()


def _config_int(config_mgr: Any | None, key: str, default: int) -> int:
    """Read one conversational-memory integer setting."""
    if config_mgr is None:
        return default
    return int(config_mgr.int_config_value("conversation_memory", key, default=default))
