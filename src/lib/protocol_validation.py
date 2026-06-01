"""Shared protocol validation fallback policy for Orac runtime clients."""
# Author: Clive Bostock
# Date: 2026-05-24
# Description: Provides explicit fail-closed handling for missing protocol validators.

from __future__ import annotations

from collections.abc import Callable
import os
from typing import Any


ALLOW_NOOP_PROTOCOL_VALIDATION_ENV = "ORAC_ALLOW_NOOP_PROTOCOL_VALIDATION"


def env_flag_enabled(value: str | None) -> bool:
    """Return whether a string environment flag is enabled."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "t", "y", "yes", "on"}


def disabled_protocol_validator(
    reason: BaseException,
) -> tuple[Callable[[dict[str, Any]], None], str]:
    """Return an explicit no-op validator only when development mode allows it.

    Args:
        reason: The exception that prevented validator initialisation.

    Returns:
        tuple[Callable[[dict[str, Any]], None], str]: Validator and protocol
        version for the explicit development fallback.

    Raises:
        RuntimeError: If protocol validation cannot be initialised and the
        explicit development override is not set.
    """
    if not env_flag_enabled(os.environ.get(ALLOW_NOOP_PROTOCOL_VALIDATION_ENV)):
        raise RuntimeError(
            "Protocol validation is unavailable. Set "
            f"{ALLOW_NOOP_PROTOCOL_VALIDATION_ENV}=true only for explicit "
            "development-mode no-op validation."
        ) from reason

    def validate_frame(_frame: dict[str, Any]) -> None:
        """Development-only protocol validator placeholder."""

    return validate_frame, "unknown"
