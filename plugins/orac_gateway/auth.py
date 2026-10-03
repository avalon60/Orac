"""Authentication and request bounds for Orac Gateway."""
# Author: Clive Bostock
# Date: 28-Sep-2026
# Description: Binds transport credentials to one host-configured Orac principal.

from __future__ import annotations

from dataclasses import dataclass
import hmac
import ipaddress
from typing import overload, Protocol, TypeVar


_T = TypeVar("_T")


class GatewayHeaderReader(Protocol):
    """Describe the header lookup operation required for authentication."""

    @overload
    def get(self, name: str, default: None = None) -> str | None:
        """Return one optional header value."""

    @overload
    def get(self, name: str, default: _T) -> str | _T:
        """Return one header value or the supplied default."""


class GatewayAuthenticationError(PermissionError):
    """Raised when an inbound gateway request is not authenticated."""


@dataclass(frozen=True, slots=True)
class GatewayIdentity:
    """Host-owned identity and restrictions for an accepted client."""

    principal: str
    allowed_models: frozenset[str] | None


class GatewayAuthenticator:
    """Authenticate bearer clients or a strictly loopback-only deployment."""

    def __init__(
        self,
        *,
        mode: str,
        principal: str,
        allowed_models: frozenset[str] | None = None,
        bearer_token: str | None = None,
    ) -> None:
        """Initialise a validated authentication policy."""
        normalised_mode = str(mode or "").strip().lower()
        if normalised_mode not in {"bearer", "trusted_loopback"}:
            raise ValueError("authentication_mode must be bearer or trusted_loopback")
        if not str(principal or "").strip():
            raise ValueError("gateway principal is required")
        if normalised_mode == "bearer" and not str(bearer_token or ""):
            raise ValueError("bearer mode requires the api_key plugin secret")
        self._mode = normalised_mode
        self._identity = GatewayIdentity(str(principal).strip(), allowed_models)
        self._bearer_token = str(bearer_token or "")

    def authenticate(
        self,
        *,
        client_host: str,
        headers: GatewayHeaderReader,
    ) -> GatewayIdentity:
        """Return the configured identity after transport authentication."""
        if self._mode == "trusted_loopback":
            try:
                is_loopback = ipaddress.ip_address(client_host).is_loopback
            except ValueError:
                is_loopback = False
            if not is_loopback:
                raise GatewayAuthenticationError(
                    "Trusted-loopback mode accepts loopback clients only."
                )
            return self._identity

        authorization = str(headers.get("Authorization") or "")
        supplied = ""
        if authorization.lower().startswith("bearer "):
            supplied = authorization[7:].strip()
        if not supplied:
            supplied = str(headers.get("X-API-Key") or "").strip()
        if not supplied or not hmac.compare_digest(supplied, self._bearer_token):
            raise GatewayAuthenticationError("A valid bearer credential is required.")
        return self._identity


def validate_listener_policy(host: str, authentication_mode: str) -> None:
    """Prevent trusted-loopback mode from binding to a non-loopback address."""
    if authentication_mode.strip().lower() != "trusted_loopback":
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        if host.strip().lower() == "localhost":
            return
    raise ValueError("trusted_loopback authentication requires a loopback listen_host")
