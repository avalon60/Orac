"""Immutable semantic embedding profile support for Core knowledge retrieval."""

# Author: Clive Bostock
# Date: 2026-09-07
# Description: Builds pinned Nomic query and document embeddings for knowledge.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests  # type: ignore[import-untyped]

from model.plugin_routing.embeddings import EmbeddingProvider
from orac_core.embedding_providers import OllamaEmbeddingProvider

from .token_accounting import ConservativeEmbeddingTokenCounter
from .token_accounting import EmbeddingInputContextExceeded


@dataclass(frozen=True)
class KnowledgeEmbeddingProfile:
    """Immutable knowledge embedding identity used across storage and retrieval."""

    provider_code: str
    model_id: str
    model_digest: str
    dimensions: int
    profile_version: str
    document_input_prefix: str
    query_input_prefix: str
    retrieval_policy_version: str
    semantic_threshold: float
    model_context_tokens: int = 2048
    context_safety_margin_tokens: int = 64
    input_estimator_code: str = "utf8_byte_upper_bound_v1"
    storage_layout_code: str = "ORACLE_VECTOR_768_FLOAT32_V1"
    truncate: bool = False


class OllamaKnowledgeEmbeddingProvider(EmbeddingProvider):
    """Generate task-prefixed Nomic embeddings for native knowledge storage."""

    semantic = True
    production_allowed = True

    def __init__(
        self,
        *,
        provider: OllamaEmbeddingProvider,
        profile: KnowledgeEmbeddingProfile,
        request_batch_size: int = 2,
    ) -> None:
        """Initialise a provider bound to one immutable profile."""
        if profile.dimensions != 768:
            raise ValueError("knowledge-v1 requires 768-dimensional embeddings")
        if profile.truncate:
            raise ValueError("knowledge embeddings must fail instead of truncating")
        if request_batch_size <= 0:
            raise ValueError("knowledge embedding request batch size must be positive")
        self._provider = provider
        self.profile = profile
        self._request_batch_size = int(request_batch_size)
        self._token_counter = ConservativeEmbeddingTokenCounter()

    @property
    def model_id(self) -> str:
        """Return the configured model tag used to call Ollama."""
        return self.profile.model_id

    @property
    def dimensions(self) -> int:
        """Return the fixed native-vector dimensions."""
        return self.profile.dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed normalized chunk text with the Nomic document prefix."""
        prefix = self.profile.document_input_prefix.rstrip()
        prefixed = [f"{prefix} {text}" for text in texts]
        self._validate_inputs(prefixed)
        vectors: list[list[float]] = []
        for offset in range(0, len(prefixed), self._request_batch_size):
            batch = prefixed[offset : offset + self._request_batch_size]
            try:
                vectors.extend(self._provider.embed_texts(batch))
            except requests.HTTPError as exc:
                response = exc.response
                detail = response.text.lower() if response is not None else ""
                if response is not None and response.status_code == 400 and (
                    "context length" in detail or "input length" in detail
                ):
                    estimates = [
                        self._token_counter.input_tokens(value) for value in batch
                    ]
                    local_index = max(
                        range(len(estimates)),
                        key=estimates.__getitem__,
                    )
                    raise EmbeddingInputContextExceeded(
                        estimated_tokens=estimates[local_index],
                        usable_limit_tokens=self.usable_input_tokens,
                        model_context_tokens=self.profile.model_context_tokens,
                        profile_identity=(
                            f"{self.profile.provider_code}:{self.profile.model_id}:"
                            f"{self.profile.model_digest}:"
                            f"{self.profile.profile_version}"
                        ),
                        input_index=offset + local_index,
                    ) from exc
                raise
        return vectors

    def embed_query(self, query: str) -> list[float]:
        """Embed one retrieval query with the Nomic query prefix."""
        prefix = self.profile.query_input_prefix.rstrip()
        prefixed = f"{prefix} {query}"
        self._validate_inputs([prefixed])
        return self._provider.embed_text(prefixed)

    @property
    def usable_input_tokens(self) -> int:
        """Return the effective context after the configured safety margin."""
        return (
            self.profile.model_context_tokens
            - self.profile.context_safety_margin_tokens
        )

    @property
    def document_content_token_limit(self) -> int:
        """Return the safe chunk budget after prefix and special-token costs."""
        prefix = self.profile.document_input_prefix.rstrip() + " "
        return max(
            1,
            self.usable_input_tokens
            - self._token_counter.input_tokens(prefix),
        )

    def count_content_tokens(self, text: str) -> int:
        """Return the profile's conservative content-token upper bound."""
        return self._token_counter.content_tokens(text)

    def validate_document_text(self, text: str) -> int:
        """Validate one document chunk and return its prefixed estimate."""
        prefix = self.profile.document_input_prefix.rstrip()
        prefixed = f"{prefix} {text}"
        self._validate_inputs([prefixed])
        return self._token_counter.input_tokens(prefixed)

    def _validate_inputs(self, inputs: list[str]) -> None:
        """Reject over-limit inputs locally without exposing their content."""
        identity = (
            f"{self.profile.provider_code}:{self.profile.model_id}:"
            f"{self.profile.model_digest}:{self.profile.profile_version}"
        )
        for index, value in enumerate(inputs):
            estimated = self._token_counter.input_tokens(value)
            if estimated > self.usable_input_tokens:
                raise EmbeddingInputContextExceeded(
                    estimated_tokens=estimated,
                    usable_limit_tokens=self.usable_input_tokens,
                    model_context_tokens=self.profile.model_context_tokens,
                    profile_identity=identity,
                    input_index=index,
                )


def knowledge_embedding_provider(
    config_mgr: Any,
) -> OllamaKnowledgeEmbeddingProvider:
    """Build and pin the configured production knowledge embedding profile."""
    section = "embedding.knowledge"
    provider_code = _value(config_mgr, section, "provider", "ollama").lower()
    if provider_code != "ollama":
        raise ValueError(
            "Production knowledge retrieval requires the Ollama semantic provider."
        )
    service_url = _value(
        config_mgr,
        section,
        "service_url",
        "http://localhost:11434",
    )
    model_id = _value(
        config_mgr,
        section,
        "model_id",
        "nomic-embed-text:latest",
    )
    dimensions = int(config_mgr.int_config_value(section, "dimensions", default=768))
    profile_version = _value(config_mgr, section, "profile_version", "knowledge-v1")
    expected_digest = _value(config_mgr, section, "model_digest", "")
    document_prefix = _value(
        config_mgr,
        section,
        "document_input_prefix",
        "search_document: ",
        strip=False,
    )
    query_prefix = _value(
        config_mgr,
        section,
        "query_input_prefix",
        "search_query: ",
        strip=False,
    )
    policy_version = _value(
        config_mgr,
        section,
        "retrieval_policy_version",
        "knowledge-hybrid-v1",
    )
    threshold = float(
        config_mgr.float_config_value(
            section,
            "semantic_threshold",
            default=0.60,
        )
    )
    if config_mgr.bool_config_value(section, "truncate", default=False):
        raise ValueError("Production knowledge embedding must use truncate=false")
    request_batch_size = int(
        config_mgr.int_config_value(section, "request_batch_size", default=2)
    )
    provider = OllamaEmbeddingProvider(
        service_url=service_url,
        model_id=model_id,
        dimensions=dimensions,
        truncate=False,
    )
    resolved_digest = provider.resolve_model_digest()
    if expected_digest and resolved_digest != expected_digest.lower():
        raise ValueError("Configured knowledge model digest does not match Ollama")
    capabilities = provider.model_capabilities()
    if int(capabilities["dimensions"]) != dimensions:
        raise ValueError("Configured knowledge dimensions do not match Ollama")
    model_context_tokens = int(capabilities["context_tokens"])
    configured_context_tokens = int(
        config_mgr.int_config_value(
            section,
            "model_context_tokens",
            default=model_context_tokens,
        )
    )
    if configured_context_tokens != model_context_tokens:
        raise ValueError("Configured knowledge context does not match Ollama")
    safety_margin = int(
        config_mgr.int_config_value(
            section,
            "context_safety_margin_tokens",
            default=64,
        )
    )
    if safety_margin < 0 or safety_margin >= model_context_tokens:
        raise ValueError("Knowledge embedding context safety margin is invalid")
    counter = ConservativeEmbeddingTokenCounter()
    profile = KnowledgeEmbeddingProfile(
        provider_code=provider_code,
        model_id=model_id,
        model_digest=resolved_digest,
        dimensions=dimensions,
        profile_version=profile_version,
        document_input_prefix=document_prefix,
        query_input_prefix=query_prefix,
        retrieval_policy_version=policy_version,
        semantic_threshold=threshold,
        model_context_tokens=model_context_tokens,
        context_safety_margin_tokens=safety_margin,
        input_estimator_code=counter.estimator_code,
    )
    return OllamaKnowledgeEmbeddingProvider(
        provider=provider,
        profile=profile,
        request_batch_size=request_batch_size,
    )


def _value(
    config_mgr: Any,
    section: str,
    key: str,
    default: str,
    *,
    strip: bool = True,
) -> str:
    """Read one required knowledge profile setting."""
    value = str(config_mgr.config_value(section, key, default=default))
    return value.strip() if strip else value
