"""Configuration for optional LLM-assisted routing arbitration."""

# Author: Clive Bostock
# Date: 20-Sep-2026
# Description: Validates the provider-neutral LLM arbitration configuration.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any
from urllib.parse import urlparse

SUPPORTED_ARBITRATION_PROVIDERS = {
    "ollama",
    "openai_compatible",
    "edge_runtime",
}


class ArbitrationConfigurationError(ValueError):
    """Raised when enabled arbitration configuration is invalid."""


@dataclass(frozen=True)
class ArbitrationConfiguration:
    """Validated settings for the optional routing adviser."""

    enabled: bool = False
    provider: str = ""
    model: str = ""
    endpoint: str = ""
    timeout_seconds: float = 10.0
    min_confidence: float = 0.90
    api_key_env: str = ""

    @classmethod
    def from_config(cls, config_mgr: Any) -> "ArbitrationConfiguration":
        """Load and validate settings from Orac's configuration manager.

        Args:
            config_mgr: Existing Orac configuration manager.

        Returns:
            Validated arbitration configuration.

        Raises:
            ArbitrationConfigurationError: If enabled settings are invalid.
        """
        try:
            enabled = bool(
                config_mgr.bool_config_value("arbitrator", "enabled", default=False)
            )
        except (TypeError, ValueError) as exc:
            raise ArbitrationConfigurationError(
                "arbitrator.enabled must be a boolean"
            ) from exc
        if not enabled:
            return cls(enabled=False)

        provider = (
            str(config_mgr.config_value("arbitrator", "provider", default=""))
            .strip()
            .lower()
        )
        model = str(config_mgr.config_value("arbitrator", "model", default="")).strip()
        endpoint = str(
            config_mgr.config_value("arbitrator", "endpoint", default="")
        ).strip()
        api_key_env = str(
            config_mgr.config_value("arbitrator", "api_key_env", default="")
        ).strip()

        if provider not in SUPPORTED_ARBITRATION_PROVIDERS:
            raise ArbitrationConfigurationError(
                "arbitrator.provider must be one of: "
                + ", ".join(sorted(SUPPORTED_ARBITRATION_PROVIDERS))
            )
        if not model:
            raise ArbitrationConfigurationError(
                "arbitrator.model is required when arbitration is enabled"
            )
        if provider in {"ollama", "openai_compatible"}:
            _validate_http_endpoint(endpoint)
        if api_key_env and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
            raise ArbitrationConfigurationError(
                "arbitrator.api_key_env must name an environment variable"
            )

        try:
            timeout_seconds = float(
                config_mgr.config_value("arbitrator", "timeout_seconds", default="10")
            )
            min_confidence = float(
                config_mgr.config_value("arbitrator", "min_confidence", default="0.90")
            )
        except (TypeError, ValueError) as exc:
            raise ArbitrationConfigurationError(
                "arbitrator timeout and confidence values must be numeric"
            ) from exc
        if not math.isfinite(timeout_seconds) or not 0.1 <= timeout_seconds <= 120.0:
            raise ArbitrationConfigurationError(
                "arbitrator.timeout_seconds must be between 0.1 and 120"
            )
        if not math.isfinite(min_confidence) or not 0.0 <= min_confidence <= 1.0:
            raise ArbitrationConfigurationError(
                "arbitrator.min_confidence must be between 0 and 1"
            )

        return cls(
            enabled=True,
            provider=provider,
            model=model,
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            min_confidence=min_confidence,
            api_key_env=api_key_env,
        )


def _validate_http_endpoint(endpoint: str) -> None:
    """Validate an HTTP provider endpoint without making a network request."""
    parsed = urlparse(endpoint)
    if not endpoint or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ArbitrationConfigurationError(
            "arbitrator.endpoint must be a non-empty HTTP(S) URL for this provider"
        )
