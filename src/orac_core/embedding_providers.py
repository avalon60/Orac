"""Shared semantic embedding providers for Orac Core capabilities."""

# Author: Clive Bostock
# Date: 2026-09-07
# Description: Provides validated provider implementations reusable by Core features.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

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
        truncate: bool | None = None,
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
        self._base_url = urlunparse(
            parsed._replace(path=base_path, params="", query="", fragment="")
        ).rstrip("/")
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
        self._truncate = truncate

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
        request_payload: dict[str, object] = {
            "model": self._model_id,
            "input": inputs,
        }
        if self._truncate is not None:
            request_payload["truncate"] = self._truncate
        response = requests.post(
            self._endpoint,
            json=request_payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        response_model = payload.get("model") if isinstance(payload, dict) else None
        if response_model is not None and str(response_model) != self._model_id:
            raise ValueError("embedding response model identity is invalid")
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

    def resolve_model_digest(self) -> str:
        """Resolve the configured tag to Ollama's immutable model digest."""
        response = requests.get(
            f"{self._base_url}/api/tags",
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise ValueError("Ollama model catalogue is invalid")
        for model in models:
            if not isinstance(model, dict):
                continue
            name = str(model.get("name") or model.get("model") or "").strip()
            if name != self._model_id:
                continue
            digest = str(model.get("digest") or "").strip().lower()
            if not digest:
                raise ValueError("Ollama model digest is missing")
            return digest
        raise ValueError(f"Ollama embedding model '{self._model_id}' is unavailable")

    def model_capabilities(self) -> dict[str, object]:
        """Return validated embedding dimensions and context from Ollama."""
        response = requests.post(
            f"{self._base_url}/api/show",
            json={"model": self._model_id},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Ollama model metadata is invalid")
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, list) or "embedding" not in capabilities:
            raise ValueError("Configured Ollama model does not support embeddings")
        model_info = payload.get("model_info")
        if not isinstance(model_info, dict):
            raise ValueError("Ollama model information is missing")
        architecture = str(model_info.get("general.architecture") or "").strip()
        context_key = f"{architecture}.context_length"
        dimensions_key = f"{architecture}.embedding_length"
        try:
            context_tokens = int(model_info[context_key])
            dimensions = int(model_info[dimensions_key])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                "Ollama embedding context or dimensions are missing"
            ) from exc
        if context_tokens <= 0 or dimensions <= 0:
            raise ValueError("Ollama embedding model limits are invalid")
        return {
            "architecture": architecture,
            "context_tokens": context_tokens,
            "dimensions": dimensions,
        }
