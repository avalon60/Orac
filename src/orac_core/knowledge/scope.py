"""Canonical scope resolution and per-user knowledge authorisation."""

# Author: Clive Bostock
# Date: 18-Jul-2026
# Description: Resolves configured dialogue scopes through approved project and plugin registries.

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping

from orac_core.plugin_registry_policy import plugin_registry_row_runtime_eligible

from .repository import default_orac_session


class KnowledgeScopeConfigurationError(ValueError):
    """Raised when dialogue knowledge scope configuration is unsafe."""


class KnowledgeScopeRegistryError(RuntimeError):
    """Raised when canonical scope registries cannot be read safely."""


@dataclass(frozen=True, slots=True, order=True)
class KnowledgeScope:
    """Canonical project or plugin scope used by ingestion and retrieval."""

    scope_type: str
    scope_key: str

    def __post_init__(self) -> None:
        """Validate and canonicalise the immutable scope."""
        scope_type = str(self.scope_type or "").strip().upper()
        scope_key = str(self.scope_key or "").strip()
        if scope_type not in {"PROJECT", "PLUGIN"}:
            raise KnowledgeScopeConfigurationError(
                "Knowledge scope type must be PROJECT or PLUGIN."
            )
        if not scope_key:
            raise KnowledgeScopeConfigurationError("Knowledge scope key is required.")
        object.__setattr__(self, "scope_type", scope_type)
        object.__setattr__(self, "scope_key", scope_key)

    @property
    def canonical_name(self) -> str:
        """Return the stable configured representation of this scope."""
        return f"{self.scope_type}:{self.scope_key}"

    @classmethod
    def parse(cls, value: str) -> KnowledgeScope:
        """Parse a canonical ``TYPE:key`` scope string."""
        scope_type, separator, scope_key = str(value or "").strip().partition(":")
        if not separator:
            raise KnowledgeScopeConfigurationError(
                f"Knowledge scope '{value}' must use TYPE:key format."
            )
        return cls(scope_type=scope_type, scope_key=scope_key)


@dataclass(frozen=True, slots=True)
class KnowledgeScopeResolution:
    """Authorisation result for one requested scope reference."""

    status: str
    reason_code: str
    scopes: tuple[KnowledgeScope, ...] = ()


@dataclass(frozen=True, slots=True)
class _RegistrySnapshot:
    """Bounded cache of currently active canonical registry scopes."""

    scopes: frozenset[KnowledgeScope]
    expires_at: float


class KnowledgeScopeRegistryRepository:
    """Read canonical active scopes through approved ``orac_code`` views."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise registry access with an injectable runtime session."""
        self._session_factory = session_factory or default_orac_session

    def load_active_scopes(self) -> frozenset[KnowledgeScope]:
        """Return all currently active project and runtime-eligible plugin scopes."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.execute("""
                    select project_code,
                           active_yn
                      from orac_code.project_registry_v
                    """)
                project_rows = cursor.fetchall()
                cursor.execute("""
                    select plugin_id,
                           install_status,
                           configuration_status,
                           dependency_status,
                           database_status,
                           readiness_status,
                           enabled
                      from orac_code.plugin_registry_v
                    """)
                columns = [item[0].lower() for item in cursor.description]
                plugin_rows = [
                    dict(zip(columns, row, strict=True)) for row in cursor.fetchall()
                ]
        except Exception as exc:
            raise KnowledgeScopeRegistryError(
                f"Unable to read canonical knowledge scope registries: {exc}"
            ) from exc
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

        scopes = {
            KnowledgeScope("PROJECT", str(project_code))
            for project_code, active_yn in project_rows
            if str(active_yn or "").upper() == "Y"
        }
        scopes.update(
            KnowledgeScope("PLUGIN", str(row["plugin_id"]))
            for row in plugin_rows
            if plugin_registry_row_runtime_eligible(row)
        )
        return frozenset(scopes)


class KnowledgeScopeAuthorizer:
    """Resolve aliases against configured grants and live canonical registries."""

    def __init__(
        self,
        *,
        user_allowlist: Mapping[str, tuple[KnowledgeScope, ...]],
        aliases: Mapping[str, KnowledgeScope],
        registry: KnowledgeScopeRegistryRepository,
        cache_ttl_seconds: int = 30,
        max_scopes_per_request: int = 3,
        logger: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialise immutable grants and bounded live-registry validation."""
        if cache_ttl_seconds <= 0:
            raise KnowledgeScopeConfigurationError(
                "registry_cache_ttl_seconds must be positive."
            )
        if max_scopes_per_request <= 0:
            raise KnowledgeScopeConfigurationError(
                "max_scopes_per_request must be positive."
            )
        self._user_allowlist = MappingProxyType(dict(user_allowlist))
        self._aliases = MappingProxyType(
            {str(name).casefold().strip(): scope for name, scope in aliases.items()}
        )
        self._registry = registry
        self._cache_ttl_seconds = cache_ttl_seconds
        self._max_scopes_per_request = max_scopes_per_request
        self._logger = logger
        self._clock = clock
        self._snapshot: _RegistrySnapshot | None = None

    @classmethod
    def from_config(
        cls,
        config_mgr: Any,
        *,
        registry: KnowledgeScopeRegistryRepository | None = None,
        logger: Any | None = None,
    ) -> KnowledgeScopeAuthorizer:
        """Build an authorizer from the exact ``knowledge.dialogue`` settings."""
        allowlist = _parse_user_allowlist(
            config_mgr.config_value(
                "knowledge.dialogue", "user_scope_allowlist_json", default="{}"
            )
        )
        aliases = _parse_aliases(
            config_mgr.config_value(
                "knowledge.dialogue", "scope_aliases_json", default="{}"
            )
        )
        return cls(
            user_allowlist=allowlist,
            aliases=aliases,
            registry=registry or KnowledgeScopeRegistryRepository(),
            cache_ttl_seconds=config_mgr.int_config_value(
                "knowledge.dialogue", "registry_cache_ttl_seconds", default=30
            ),
            max_scopes_per_request=config_mgr.int_config_value(
                "knowledge.dialogue", "max_scopes_per_request", default=3
            ),
            logger=logger,
        )

    def validate_startup(self) -> KnowledgeScopeResolution:
        """Validate all configured grants and aliases against current registries."""
        try:
            active = self._active_scopes(force_refresh=True)
        except KnowledgeScopeRegistryError:
            return KnowledgeScopeResolution("unavailable", "scope_registry_unavailable")
        configured = {
            scope for scopes in self._user_allowlist.values() for scope in scopes
        } | set(self._aliases.values())
        invalid = configured - active
        if invalid:
            self._log_warning(
                "Knowledge dialogue configuration references unknown or inactive "
                "scopes: "
                + ", ".join(sorted(scope.canonical_name for scope in invalid))
            )
            return KnowledgeScopeResolution("degraded", "configured_scope_inactive")
        return KnowledgeScopeResolution("ready", "scope_configuration_valid")

    def resolve_for_user(
        self,
        username: str,
        requested_names: tuple[str, ...],
    ) -> KnowledgeScopeResolution:
        """Resolve requested aliases/canonical names and enforce current user grants."""
        canonical_user = str(username or "").strip()
        if not canonical_user or canonical_user not in self._user_allowlist:
            return KnowledgeScopeResolution("denied", "user_scope_allowlist_missing")
        if not requested_names:
            return KnowledgeScopeResolution("ambiguous", "knowledge_scope_required")
        if len(requested_names) > self._max_scopes_per_request:
            return KnowledgeScopeResolution("denied", "knowledge_scope_limit_exceeded")

        resolved: list[KnowledgeScope] = []
        for requested_name in requested_names:
            requested = str(requested_name or "").strip()
            try:
                scope = (
                    KnowledgeScope.parse(requested)
                    if ":" in requested
                    else self._aliases[requested.casefold()]
                )
            except (KeyError, KnowledgeScopeConfigurationError):
                return KnowledgeScopeResolution("unknown", "knowledge_scope_unknown")
            if scope not in resolved:
                resolved.append(scope)

        grants = set(self._user_allowlist[canonical_user])
        if any(scope not in grants for scope in resolved):
            return KnowledgeScopeResolution("denied", "knowledge_scope_not_authorised")
        try:
            active = self._active_scopes()
        except KnowledgeScopeRegistryError:
            return KnowledgeScopeResolution("unavailable", "scope_registry_unavailable")
        if any(scope not in active for scope in resolved):
            return KnowledgeScopeResolution("inactive", "knowledge_scope_inactive")
        return KnowledgeScopeResolution(
            "authorised", "knowledge_scope_authorised", tuple(resolved)
        )

    @property
    def aliases(self) -> Mapping[str, KnowledgeScope]:
        """Return immutable configured aliases for deterministic route detection."""
        return self._aliases

    @property
    def max_scopes_per_request(self) -> int:
        """Return the configured per-request scope limit."""
        return self._max_scopes_per_request

    def _active_scopes(
        self, *, force_refresh: bool = False
    ) -> frozenset[KnowledgeScope]:
        """Return a fresh registry snapshot or fail closed after expiry."""
        now = self._clock()
        if (
            not force_refresh
            and self._snapshot is not None
            and now < self._snapshot.expires_at
        ):
            return self._snapshot.scopes
        scopes = self._registry.load_active_scopes()
        self._snapshot = _RegistrySnapshot(
            scopes=scopes,
            expires_at=now + self._cache_ttl_seconds,
        )
        return scopes

    def _log_warning(self, message: str) -> None:
        """Emit a safe operational warning when a logger is available."""
        method = getattr(self._logger, "log_warning", None)
        if callable(method):
            method(message)


def _load_json_object(source: str, *, setting_name: str) -> dict[str, Any]:
    """Parse a JSON object while rejecting duplicate object keys."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise KnowledgeScopeConfigurationError(
                    f"{setting_name} contains duplicate key '{key}'."
                )
            result[key] = value
        return result

    try:
        value = json.loads(source, object_pairs_hook=reject_duplicates)
    except json.JSONDecodeError as exc:
        raise KnowledgeScopeConfigurationError(
            f"{setting_name} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise KnowledgeScopeConfigurationError(f"{setting_name} must be a JSON object.")
    return value


def _parse_user_allowlist(source: str) -> Mapping[str, tuple[KnowledgeScope, ...]]:
    """Parse exact authenticated usernames to deduplicated canonical scopes."""
    raw = _load_json_object(source, setting_name="user_scope_allowlist_json")
    parsed: dict[str, tuple[KnowledgeScope, ...]] = {}
    for username, values in raw.items():
        if not username.strip() or not isinstance(values, list):
            raise KnowledgeScopeConfigurationError(
                "user_scope_allowlist_json values must be arrays keyed by username."
            )
        scopes: list[KnowledgeScope] = []
        for value in values:
            if not isinstance(value, str) or value == "*":
                raise KnowledgeScopeConfigurationError(
                    "Knowledge allowlists accept canonical TYPE:key strings only."
                )
            scope = KnowledgeScope.parse(value)
            if scope not in scopes:
                scopes.append(scope)
        parsed[username] = tuple(scopes)
    return MappingProxyType(parsed)


def _parse_aliases(source: str) -> Mapping[str, KnowledgeScope]:
    """Parse unique case-insensitive aliases to canonical scopes."""
    raw = _load_json_object(source, setting_name="scope_aliases_json")
    parsed: dict[str, KnowledgeScope] = {}
    for alias, value in raw.items():
        normalised_alias = alias.casefold().strip()
        if not normalised_alias or not isinstance(value, str):
            raise KnowledgeScopeConfigurationError(
                "scope_aliases_json must map non-empty aliases to TYPE:key strings."
            )
        if normalised_alias in parsed:
            raise KnowledgeScopeConfigurationError(
                f"scope_aliases_json contains ambiguous alias '{alias}'."
            )
        parsed[normalised_alias] = KnowledgeScope.parse(value)
    return MappingProxyType(parsed)
