"""Shared semantic embedding providers for Orac Core capabilities."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Provides validated provider implementations reusable by Core features.

from __future__ import annotations

import math
from urllib.parse import urlparse, urlunparse

import requests  # type: ignore[import-untyped]

from model.plugin_routing.embeddings import EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
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
        """Initialise one pinned embedding profile."""
        parsed = urlparse(str(service_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("embedding service URL must be HTTP(S)")
        model = str(model_id or "").strip()
        if not model:
            raise ValueError("embedding model id is required")
        if dimensions <= 0:
            raise ValueError("embedding dimensions must be positive")
        base_path = parsed.path.rstrip("/")
        self._endpoint = urlunparse(
            parsed._replace(
                path=f"{base_path}/api/embed", params="", query="", fragment=""
            )
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

    @property
    def dimensions(self) -> int:
        """Return the configured vector dimensions."""
        return self._dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return finite, dimension-checked embeddings for every input text."""
        if not texts:
            return []
        inputs = [str(item or "").strip() for item in texts]
        if any(not item for item in inputs):
            raise ValueError("embedding input must not be empty")
        response = requests.post(
            self._endpoint,
            json={"model": self._model_id, "input": inputs},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        vectors = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(vectors, list) or len(vectors) != len(inputs):
            raise ValueError("embedding response count is invalid")

        validated: list[list[float]] = []
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != self._dimensions:
                raise ValueError("embedding dimensions are invalid")
            values = [float(item) for item in vector]
            if any(not math.isfinite(item) for item in values):
                raise ValueError("embedding contains non-finite values")
            validated.append(values)
        return validated
