"""Trusted confirmation broker for risky plugin execution."""
# Author: Clive Bostock
# Date: 2026-05-25
# Description: Tracks Orac-owned confirmation state for plugin actions.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import uuid

from model.plugin_routing.models import PluginExecutionPolicy
from model.plugin_routing.models import PluginManifest


@dataclass(frozen=True)
class PluginConfirmationRequest:
    """Represents one pending Orac-owned plugin confirmation request."""

    confirmation_id: str
    plugin_id: str
    plugin_name: str
    action_type: str
    capabilities: tuple[str, ...]
    action_summary: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class PluginConfirmationDecision:
    """Represents a trusted confirmation validation result."""

    confirmed: bool
    status: str
    reason: str | None
    confirmation_id: str | None = None
    request: PluginConfirmationRequest | None = None


@dataclass
class _ConfirmationRecord:
    """Mutable internal confirmation request state."""

    request: PluginConfirmationRequest
    confirmed_at: datetime | None = None
    consumed_at: datetime | None = None


class PluginConfirmationBroker:
    """Issue and validate trusted plugin action confirmations."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 300,
        now: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        """Initialise the in-memory confirmation broker.

        Args:
            ttl_seconds: Default lifetime for newly issued confirmations.
            now: Optional clock injection for tests.
            token_factory: Optional id generator injection for tests.
        """
        self._ttl_seconds = ttl_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._token_factory = token_factory or (lambda: uuid.uuid4().hex)
        self._records: dict[str, _ConfirmationRecord] = {}

    def create_request(
        self,
        manifest: PluginManifest,
        policy: PluginExecutionPolicy,
        *,
        action_summary: str | None = None,
        ttl_seconds: int | None = None,
    ) -> PluginConfirmationRequest:
        """Create and store a pending confirmation request for a plugin action."""
        created_at = self._coerce_utc(self._now())
        expires_at = created_at + timedelta(
            seconds=ttl_seconds if ttl_seconds is not None else self._ttl_seconds
        )
        confirmation_id = self._token_factory()
        request = PluginConfirmationRequest(
            confirmation_id=confirmation_id,
            plugin_id=manifest.plugin_id,
            plugin_name=manifest.name,
            action_type=str(policy.action_type),
            capabilities=tuple(policy.capabilities or manifest.capabilities),
            action_summary=(
                action_summary
                or f"{manifest.name} requested {policy.action_type} access."
            ),
            created_at=created_at,
            expires_at=expires_at,
        )
        self._records[confirmation_id] = _ConfirmationRecord(request=request)
        return request

    def confirm_request(self, confirmation_id: str) -> PluginConfirmationDecision:
        """Record an explicit trusted confirmation for a pending request."""
        record = self._records.get(confirmation_id)
        if record is None:
            return PluginConfirmationDecision(
                confirmed=False,
                status="not_found",
                reason="Confirmation id was not issued by Orac.",
                confirmation_id=confirmation_id,
            )
        if record.consumed_at is not None:
            return PluginConfirmationDecision(
                confirmed=False,
                status="replayed",
                reason="Confirmation has already been consumed.",
                confirmation_id=confirmation_id,
                request=record.request,
            )
        if self._is_expired(record):
            return PluginConfirmationDecision(
                confirmed=False,
                status="expired",
                reason="Confirmation request has expired.",
                confirmation_id=confirmation_id,
                request=record.request,
            )
        record.confirmed_at = self._coerce_utc(self._now())
        return PluginConfirmationDecision(
            confirmed=True,
            status="confirmed",
            reason=None,
            confirmation_id=confirmation_id,
            request=record.request,
        )

    def consume_confirmation(
        self,
        *,
        confirmation_id: str | None,
        manifest: PluginManifest,
        policy: PluginExecutionPolicy,
    ) -> PluginConfirmationDecision:
        """Validate and consume a trusted confirmation for one plugin action."""
        if not confirmation_id:
            return PluginConfirmationDecision(
                confirmed=False,
                status="missing",
                reason="No broker-issued confirmation id was supplied.",
            )

        record = self._records.get(confirmation_id)
        if record is None:
            return PluginConfirmationDecision(
                confirmed=False,
                status="not_found",
                reason="Confirmation id was not issued by Orac.",
                confirmation_id=confirmation_id,
            )
        if record.consumed_at is not None:
            return PluginConfirmationDecision(
                confirmed=False,
                status="replayed",
                reason="Confirmation has already been consumed.",
                confirmation_id=confirmation_id,
                request=record.request,
            )
        if self._is_expired(record):
            return PluginConfirmationDecision(
                confirmed=False,
                status="expired",
                reason="Confirmation request has expired.",
                confirmation_id=confirmation_id,
                request=record.request,
            )
        if record.confirmed_at is None:
            return PluginConfirmationDecision(
                confirmed=False,
                status="pending",
                reason="Confirmation request has not been approved.",
                confirmation_id=confirmation_id,
                request=record.request,
            )
        if not self._matches_request(record.request, manifest, policy):
            return PluginConfirmationDecision(
                confirmed=False,
                status="mismatch",
                reason="Confirmation does not match the requested plugin action.",
                confirmation_id=confirmation_id,
                request=record.request,
            )

        record.consumed_at = self._coerce_utc(self._now())
        return PluginConfirmationDecision(
            confirmed=True,
            status="confirmed",
            reason=None,
            confirmation_id=confirmation_id,
            request=record.request,
        )

    def _is_expired(self, record: _ConfirmationRecord) -> bool:
        """Return whether a confirmation record is expired."""
        return self._coerce_utc(self._now()) >= self._coerce_utc(record.request.expires_at)

    @staticmethod
    def _matches_request(
        request: PluginConfirmationRequest,
        manifest: PluginManifest,
        policy: PluginExecutionPolicy,
    ) -> bool:
        """Return whether the confirmation request matches current action metadata."""
        return (
            request.plugin_id == manifest.plugin_id
            and request.action_type == str(policy.action_type)
            and request.capabilities == tuple(policy.capabilities or manifest.capabilities)
        )

    @staticmethod
    def _coerce_utc(value: datetime) -> datetime:
        """Return a timezone-aware UTC datetime."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
