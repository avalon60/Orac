"""Map per-person local or provider tokens to existing Orac principals."""
# Author: Clive Bostock
# Date: 11-Oct-2026
# Description: Authenticates MCP transport calls without granting knowledge access.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import hmac
from typing import Mapping

import jwt
from jwt import PyJWKClient


class McpAuthenticationError(PermissionError):
    """Raised when transport identity cannot be established."""


class McpAuthenticator:
    """Authenticate a bearer token and resolve one administrator-bound user."""

    def __init__(
        self,
        *,
        local_tokens: Mapping[str, str] | None = None,
        issuer: str | None = None,
        audience: str | None = None,
        jwks_url: str | None = None,
        subject_bindings: Mapping[str, str] | None = None,
    ) -> None:
        """Select local token or externally issued JWT authentication."""
        if local_tokens is not None:
            if not local_tokens or any(
                not token or not user for token, user in local_tokens.items()
            ):
                raise ValueError("Every local credential requires a principal.")
            self._local_tokens = dict(local_tokens)
            self._issuer = None
            self._audience = None
            self._subjects: dict[str, str] = {}
            self._jwks = None
        else:
            if (
                not issuer
                or not issuer.startswith("https://")
                or not audience
                or not audience.startswith("https://")
                or not jwks_url
                or not jwks_url.startswith("https://")
                or not subject_bindings
            ):
                raise ValueError(
                    "External identity requires HTTPS issuer, audience and JWKS."
                )
            self._local_tokens = None
            self._issuer = issuer
            self._audience = audience
            self._subjects = dict(subject_bindings)
            self._jwks = PyJWKClient(jwks_url, cache_keys=True, lifespan=300, timeout=5)

    @property
    def issuer(self) -> str | None:
        """Return the configured external issuer for resource discovery."""
        return self._issuer

    @property
    def audience(self) -> str | None:
        """Return the configured protected resource URL."""
        return self._audience

    def authenticate(self, authorization: str | None) -> str:
        """Return the mapped principal or deny the request."""
        value = str(authorization or "")
        if not value.lower().startswith("bearer "):
            raise McpAuthenticationError("Authentication required.")
        token = value[7:].strip()
        if not token or len(token) > 16384:
            raise McpAuthenticationError("Authentication required.")
        if self._local_tokens is not None:
            for expected, principal in self._local_tokens.items():
                if hmac.compare_digest(token, expected):
                    return principal
            raise McpAuthenticationError("Authentication required.")
        try:
            assert self._jwks is not None
            key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except (jwt.PyJWTError, OSError, ValueError) as exc:
            raise McpAuthenticationError("Authentication required.") from exc
        principal = self._subjects.get(str(claims["sub"]))
        if not principal:
            raise McpAuthenticationError("Authentication required.")
        return principal
