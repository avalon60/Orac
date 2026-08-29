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
        if project_scope is not None and not project_scope.upper().startswith("PROJECT:"):
            raise ValueError("governed_retrieval.project_scope must use PROJECT:key")
        object.__setattr__(self, "project_scope", project_scope)

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
            project_scope=config_mgr.config_value(
                section, "project_scope", default=""
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
