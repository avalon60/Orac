"""Validated configuration for Phase 2A governed retrieval."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Owns conservative bounded commit-gate and evidence settings.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GovernedRetrievalConfiguration:
    """Validated Phase 2A settings read only from host configuration."""

    enabled: bool = False
    stream_commit_delay_ms: int = 350
    stream_commit_max_characters: int = 128
    max_evidence_tokens: int = 1200
    context_safety_tokens: int = 256
    project_scope: str | None = None
    domain_discovery_enabled: bool = False
    domain_discovery_shadow_mode: bool = True
    descriptor_embedding_profile: str = "domain_discovery"
    domain_descriptor_schema_version: str = "domain-descriptor-v1"
    domain_min_relevance_score: float = 0.50
    domain_semantic_weight: float = 0.85
    domain_lexical_weight: float = 0.15
    domain_embedding_batch_size: int = 64
    domain_catalogue_hard_limit: int = 4096
    max_advertised_domains: int = 3
    max_selected_domains: int = 2
    max_catalogue_characters: int = 2000
    max_federated_evidence_items: int = 6

    MIN_COMMIT_DELAY_MS = 100
    MAX_COMMIT_DELAY_MS = 1000
    MIN_COMMIT_CHARACTERS = 32
    MAX_COMMIT_CHARACTERS = 512
    MIN_EVIDENCE_TOKENS = 64
    MAX_EVIDENCE_TOKENS = 4096
    MIN_CONTEXT_SAFETY_TOKENS = 128
    MAX_CONTEXT_SAFETY_TOKENS = 4096

    def __post_init__(self) -> None:
        """Reject unsafe settings instead of silently clamping them."""
        self._validate_bound(
            "stream_commit_delay_ms",
            self.stream_commit_delay_ms,
            self.MIN_COMMIT_DELAY_MS,
            self.MAX_COMMIT_DELAY_MS,
        )
        self._validate_bound(
            "stream_commit_max_characters",
            self.stream_commit_max_characters,
            self.MIN_COMMIT_CHARACTERS,
            self.MAX_COMMIT_CHARACTERS,
        )
        self._validate_bound(
            "max_evidence_tokens",
            self.max_evidence_tokens,
            self.MIN_EVIDENCE_TOKENS,
            self.MAX_EVIDENCE_TOKENS,
        )
        self._validate_bound(
            "context_safety_tokens",
            self.context_safety_tokens,
            self.MIN_CONTEXT_SAFETY_TOKENS,
            self.MAX_CONTEXT_SAFETY_TOKENS,
        )
        project_scope = str(self.project_scope or "").strip() or None
        if project_scope is not None and not project_scope.upper().startswith(
            "PROJECT:"
        ):
            raise ValueError("governed_retrieval.project_scope must use PROJECT:key")
        object.__setattr__(self, "project_scope", project_scope)
        if self.descriptor_embedding_profile != "domain_discovery":
            raise ValueError(
                "governed_retrieval.descriptor_embedding_profile must be "
                "domain_discovery"
            )
        if not str(self.domain_descriptor_schema_version or "").strip():
            raise ValueError("domain descriptor schema version is required")
        for name, value, minimum, maximum in (
            ("domain_embedding_batch_size", self.domain_embedding_batch_size, 1, 512),
            (
                "domain_catalogue_hard_limit",
                self.domain_catalogue_hard_limit,
                128,
                10000,
            ),
            ("max_advertised_domains", self.max_advertised_domains, 1, 8),
            ("max_selected_domains", self.max_selected_domains, 1, 3),
            ("max_catalogue_characters", self.max_catalogue_characters, 256, 8000),
            ("max_federated_evidence_items", self.max_federated_evidence_items, 1, 20),
        ):
            self._validate_bound(name, value, minimum, maximum)
        if self.max_selected_domains > self.max_advertised_domains:
            raise ValueError("maximum selected domains cannot exceed advertisements")
        if not 0.0 <= self.domain_min_relevance_score <= 1.0:
            raise ValueError("domain minimum relevance score must be between 0 and 1")
        if self.domain_semantic_weight < 0 or self.domain_lexical_weight < 0:
            raise ValueError("domain discovery weights must not be negative")
        if abs(self.domain_semantic_weight + self.domain_lexical_weight - 1.0) > 1e-9:
            raise ValueError("domain discovery weights must sum to 1")

    @classmethod
    def from_config(cls, config_mgr: Any) -> "GovernedRetrievalConfiguration":
        """Load Phase 2A configuration using established ConfigManager accessors."""
        section = "governed_retrieval"
        return cls(
            enabled=config_mgr.bool_config_value(section, "enabled", default=False),
            stream_commit_delay_ms=config_mgr.int_config_value(
                section, "stream_commit_delay_ms", default=350
            ),
            stream_commit_max_characters=config_mgr.int_config_value(
                section, "stream_commit_max_characters", default=128
            ),
            max_evidence_tokens=config_mgr.int_config_value(
                section, "max_evidence_tokens", default=1200
            ),
            context_safety_tokens=config_mgr.int_config_value(
                section, "context_safety_tokens", default=256
            ),
            project_scope=config_mgr.config_value(section, "project_scope", default=""),
            domain_discovery_enabled=config_mgr.bool_config_value(
                section, "domain_discovery_enabled", default=False
            ),
            domain_discovery_shadow_mode=config_mgr.bool_config_value(
                section, "domain_discovery_shadow_mode", default=True
            ),
            descriptor_embedding_profile=config_mgr.config_value(
                section,
                "descriptor_embedding_profile",
                default="domain_discovery",
            ),
            domain_descriptor_schema_version=config_mgr.config_value(
                section,
                "domain_descriptor_schema_version",
                default="domain-descriptor-v1",
            ),
            domain_min_relevance_score=_float_config(
                config_mgr, section, "domain_min_relevance_score", 0.50
            ),
            domain_semantic_weight=_float_config(
                config_mgr, section, "domain_semantic_weight", 0.85
            ),
            domain_lexical_weight=_float_config(
                config_mgr, section, "domain_lexical_weight", 0.15
            ),
            domain_embedding_batch_size=config_mgr.int_config_value(
                section, "domain_embedding_batch_size", default=64
            ),
            domain_catalogue_hard_limit=config_mgr.int_config_value(
                section, "domain_catalogue_hard_limit", default=4096
            ),
            max_advertised_domains=config_mgr.int_config_value(
                section, "max_advertised_domains", default=3
            ),
            max_selected_domains=config_mgr.int_config_value(
                section, "max_selected_domains", default=2
            ),
            max_catalogue_characters=config_mgr.int_config_value(
                section, "max_catalogue_characters", default=2000
            ),
            max_federated_evidence_items=config_mgr.int_config_value(
                section, "max_federated_evidence_items", default=6
            ),
        )

    @staticmethod
    def _validate_bound(name: str, value: int, minimum: int, maximum: int) -> None:
        """Validate one integer setting against strict inclusive bounds."""
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"governed_retrieval.{name} must be an integer")
        if not minimum <= value <= maximum:
            raise ValueError(
                f"governed_retrieval.{name} must be between {minimum} and {maximum}"
            )


def _float_config(
    config_mgr: Any,
    section: str,
    key: str,
    default: float,
) -> float:
    """Read a float through either the full or lightweight config contract."""
    reader = getattr(config_mgr, "float_config_value", None)
    if callable(reader):
        return float(reader(section, key, default=default))
    return float(config_mgr.config_value(section, key, default=str(default)))
