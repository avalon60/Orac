"""Validated runtime configuration for Orac Gateway."""
# Author: Clive Bostock
# Date: 28-Sep-2026
# Description: Loads bounded gateway configuration from the plugin scope.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .auth import validate_listener_policy


class GatewayConfigReader(Protocol):
    """Describe the read-only plugin configuration methods used here."""

    def config_value(
        self,
        section: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Return one scoped configuration value."""

    def int_config_value(
        self,
        section: str,
        key: str,
        default: int | None = None,
    ) -> int:
        """Return one scoped integer configuration value."""


@dataclass(frozen=True, slots=True)
class GatewayConfiguration:
    """Configuration accepted by the managed gateway service."""

    listen_host: str
    listen_port: int
    authentication_mode: str
    principal: str
    allowed_models: frozenset[str] | None
    max_request_bytes: int

    @classmethod
    def from_manager(cls, manager: GatewayConfigReader) -> "GatewayConfiguration":
        """Load and validate configuration from ``PluginConfigManager``."""
        host = str(manager.config_value("gateway", "listen_host", "127.0.0.1")).strip()
        port = manager.int_config_value("gateway", "listen_port", 11435)
        mode = str(
            manager.config_value("gateway", "authentication_mode", "trusted_loopback")
        ).strip().lower()
        principal = str(
            manager.config_value("gateway", "principal", "orac_gateway")
        ).strip()
        raw_models = str(manager.config_value("gateway", "allowed_models", ""))
        models = frozenset(
            item.strip() for item in raw_models.split(",") if item.strip()
        ) or None
        maximum = manager.int_config_value("gateway", "max_request_bytes", 1048576)
        if not host:
            raise ValueError("listen_host is required")
        if not 1 <= port <= 65535:
            raise ValueError("listen_port must be between 1 and 65535")
        if not principal:
            raise ValueError("principal is required")
        if not 1024 <= maximum <= 16 * 1024 * 1024:
            raise ValueError("max_request_bytes must be between 1024 and 16777216")
        validate_listener_policy(host, mode)
        return cls(host, port, mode, principal, models, maximum)
