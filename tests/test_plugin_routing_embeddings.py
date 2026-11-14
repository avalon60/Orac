"""Verify dedicated production routing embeddings and cache identity isolation."""

# Author: Clive Bostock
# Date: 12-Nov-2026
# Description: Test explicit semantic routing profiles without network requests.
# Purpose: Keep deterministic fixtures out of production plugin routing.
# Usage: PYTHONPATH=src .venv/bin/python -m pytest tests/test_plugin_routing_embeddings.py
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from orac_core.plugin_routing_embeddings import plugin_routing_embedding_provider
from model.plugin_routing.cache import PluginEmbeddingCache


class Config:
    """Expose only the dedicated routing section to detect accidental inheritance."""

    def __init__(self, **overrides):
        """Create a complete small explicit routing profile."""
        self.values = (
            dict(
                embedding_provider="ollama",
                embedding_service_url="http://localhost:11434",
                embedding_model_id="nomic-embed-text:latest",
                embedding_dimensions=3,
                embedding_profile_version="routing-v1",
            )
            | overrides
        )

    def config_value(self, section, key, default=None):
        """Read routing-only string settings."""
        assert section == "plugin_routing"
        return self.values.get(key, default)

    def int_config_value(self, section, key, default=None):
        """Read routing-only integer settings."""
        assert section == "plugin_routing"
        return int(self.values.get(key, default))


def test_real_model_is_sent_but_cache_uses_dedicated_profile(monkeypatch, tmp_path):
    """Delegation preserves intent text and real Ollama identity without cache collisions."""
    response = SimpleNamespace(
        raise_for_status=Mock(),
        json=lambda: {
            "model": "nomic-embed-text:latest",
            "embeddings": [[1.0, 0.0, 0.0]],
        },
    )
    post = Mock(return_value=response)
    monkeypatch.setattr("orac_core.embedding_providers.requests.post", post)
    provider = plugin_routing_embedding_provider(Config())
    assert provider.semantic and provider.production_allowed
    assert provider.embed_texts(["canonical intent text"]) == [[1.0, 0.0, 0.0]]
    assert post.call_args.kwargs["json"] == {
        "model": "nomic-embed-text:latest",
        "input": ["canonical intent text"],
    }
    assert provider.model_id.startswith("plugin-routing:")
    assert "http://" not in provider.model_id
    cache = PluginEmbeddingCache(tmp_path)
    assert cache._cache_path(provider.model_id) != cache._cache_path(
        "nomic-embed-text:latest"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"embedding_service_url": "http://localhost:11435"},
        {"embedding_model_id": "nomic-embed-text:other"},
        {"embedding_dimensions": 4},
        {"embedding_profile_version": "routing-v2"},
    ],
)
def test_routing_profile_changes_invalidate_cache_identity(change):
    """Endpoint, model, dimensions and profile changes never share stale vectors."""
    assert (
        plugin_routing_embedding_provider(Config()).model_id
        != plugin_routing_embedding_provider(Config(**change)).model_id
    )


@pytest.mark.parametrize(
    "change",
    [
        {"embedding_provider": ""},
        {"embedding_provider": "hash"},
        {"embedding_provider": "deterministic"},
        {"embedding_service_url": ""},
        {"embedding_service_url": "http://name:password@localhost:11434"},
        {"embedding_model_id": ""},
        {"embedding_dimensions": 0},
        {"embedding_profile_version": ""},
    ],
)
def test_missing_or_nonproduction_profile_fails_closed(change):
    """Production configuration cannot select a fixture or inherit another domain profile."""
    with pytest.raises(ValueError):
        plugin_routing_embedding_provider(Config(**change))


def test_provider_http_failure_never_returns_hash_vectors(monkeypatch):
    """An unavailable semantic provider propagates to the existing routing failure path."""
    post = Mock(side_effect=RuntimeError("offline"))
    monkeypatch.setattr("orac_core.embedding_providers.requests.post", post)
    provider = plugin_routing_embedding_provider(Config())
    with pytest.raises(RuntimeError, match="offline"):
        provider.embed_texts(["canonical intent text"])
    assert post.call_count == 1
