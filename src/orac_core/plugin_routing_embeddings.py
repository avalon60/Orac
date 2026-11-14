"""Build dedicated semantic embeddings for Core plugin routing."""

# Author: Clive Bostock
# Date: 12-Nov-2026
# Description: Resolve an explicit routing-only Ollama profile and cache identity.
# Purpose: Keep non-semantic test fixtures out of production routing bootstrap.
# Usage: plugin_routing_embedding_provider(config_mgr) supplies PluginManager.
from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from model.plugin_routing.embeddings import EmbeddingProvider
from orac_core.embedding_providers import OllamaEmbeddingProvider


class PluginRoutingEmbeddingProvider(EmbeddingProvider):
    """Adapt a semantic provider while isolating its routing cache identity."""

    semantic = True
    production_allowed = True

    def __init__(self, provider: OllamaEmbeddingProvider, cache_model_id: str) -> None:
        """Store the real provider separately from its cache-facing profile ID."""
        self._provider = provider
        self._cache_model_id = cache_model_id

    @property
    def model_id(self) -> str:
        """Return the routing-specific provider/endpoint/model/dimension identity."""
        return self._cache_model_id

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Delegate unchanged canonical intent text to the real semantic provider."""
        return self._provider.embed_texts(texts)


def plugin_routing_embedding_provider(config_mgr: Any) -> EmbeddingProvider:
    """Build the explicitly configured semantic routing provider.

    Args:
        config_mgr: Host configuration reader for the plugin_routing section.

    Returns:
        A production semantic adapter with a dedicated cache identity.

    Raises:
        ValueError: If the dedicated profile is missing, malformed or unsupported.
    """

    def setting(key: str) -> str:
        return str(
            config_mgr.config_value("plugin_routing", key, default="") or ""
        ).strip()

    provider_code = setting("embedding_provider").lower()
    if provider_code != "ollama":
        raise ValueError(
            "Plugin routing requires an explicit supported semantic provider"
        )
    service_url, model_id = setting("embedding_service_url"), setting(
        "embedding_model_id"
    )
    profile_version = setting("embedding_profile_version")
    dimensions = int(
        config_mgr.int_config_value("plugin_routing", "embedding_dimensions", default=0)
    )
    if not profile_version or not re.fullmatch(
        r"[A-Za-z0-9._-]{1,64}", profile_version
    ):
        raise ValueError("Plugin routing embedding profile version is required")
    parsed = urlsplit(service_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Plugin routing embedding endpoint must be a plain HTTP(S) service URL"
        )
    endpoint = urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", "")
    )
    provider = OllamaEmbeddingProvider(
        service_url=endpoint, model_id=model_id, dimensions=dimensions
    )
    endpoint_fingerprint = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:16]
    identity = json.dumps(
        {
            "scope": "plugin-routing",
            "provider": provider_code,
            "endpoint": endpoint_fingerprint,
            "model": model_id,
            "dimensions": dimensions,
            "profile_version": profile_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return PluginRoutingEmbeddingProvider(provider, "plugin-routing:" + identity)
