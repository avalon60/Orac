"""Embedding-provider selection for conversational memory."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Provides validated local semantic embeddings for conversation recall.

from __future__ import annotations

from typing import Any

import requests  # type: ignore[import-untyped]  # compatibility patch seam

from orac_core.embedding_providers import OllamaEmbeddingProvider
from model.plugin_routing.embeddings import EmbeddingProvider
from model.plugin_routing.embeddings import HashEmbeddingProvider


class OllamaConversationEmbeddingProvider(OllamaEmbeddingProvider):
    """Compatibility name for the shared Ollama embedding provider."""


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
    raise ValueError(f"unsupported conversation embedding provider '{provider_code}'")


def _config_value(config_mgr: Any | None, key: str, default: str) -> str:
    """Read one conversational-memory string setting."""
    if config_mgr is None:
        return default
    return str(
        config_mgr.config_value("conversation_memory", key, default=default)
    ).strip()


def _config_int(config_mgr: Any | None, key: str, default: int) -> int:
    """Read one conversational-memory integer setting."""
    if config_mgr is None:
        return default
    return int(config_mgr.int_config_value("conversation_memory", key, default=default))
