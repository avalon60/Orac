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


class RagUsageAuthorizationRepository:
    """Call the least-privilege database RAG usage decision API."""

    _PACKAGE = "orac_code.rag_usage_authorization_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise authorization access with an injectable runtime session."""
        self._session_factory = session_factory or default_orac_session

    def authorization_result(self, username: str, scope: KnowledgeScope) -> str:
        """Return the database decision code for one principal and scope."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                result = cursor.callfunc(
                    f"{self._PACKAGE}.authorization_result",
                    str,
                    [username, scope.scope_type, scope.scope_key],
                )
            return str(result or "RAG_USAGE_AUTHORIZATION_UNAVAILABLE")
        except Exception as exc:
            raise KnowledgeScopeRegistryError(
                "RAG usage authorization service is unavailable."
            ) from exc
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()


class KnowledgeScopeAuthorizer:
    """Resolve aliases against database privileges and live scope registries."""

    def __init__(
        self,
        *,
        aliases: Mapping[str, KnowledgeScope],
        registry: KnowledgeScopeRegistryRepository,
        authorization_repository: RagUsageAuthorizationRepository,
        allow_all_scopes: bool = False,
        cache_ttl_seconds: int = 30,
        max_scopes_per_request: int = 3,
        logger: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialise database authorization and bounded registry validation."""
        if cache_ttl_seconds <= 0:
            raise KnowledgeScopeConfigurationError(
                "registry_cache_ttl_seconds must be positive."
            )
        if max_scopes_per_request <= 0:
            raise KnowledgeScopeConfigurationError(
                "max_scopes_per_request must be positive."
            )
        self._aliases = MappingProxyType(
            {str(name).casefold().strip(): scope for name, scope in aliases.items()}
        )
        self._registry = registry
        self._authorization_repository = authorization_repository
        self._allow_all_scopes = bool(allow_all_scopes)
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
        authorization_repository: RagUsageAuthorizationRepository | None = None,
        logger: Any | None = None,
    ) -> KnowledgeScopeAuthorizer:
        """Build an authorizer from the exact ``knowledge.dialogue`` settings."""
        cls.validate_config(config_mgr)
        aliases = _parse_aliases(
            config_mgr.config_value(
                "knowledge.dialogue", "scope_aliases_json", default="{}"
            )
        )
        return cls(
            aliases=aliases,
            registry=registry or KnowledgeScopeRegistryRepository(),
            authorization_repository=(
                authorization_repository or RagUsageAuthorizationRepository()
            ),
            allow_all_scopes=config_mgr.bool_config_value(
                "knowledge.dialogue", "allow_all_scopes", default=False
            ),
            cache_ttl_seconds=config_mgr.int_config_value(
                "knowledge.dialogue", "registry_cache_ttl_seconds", default=30
            ),
            max_scopes_per_request=config_mgr.int_config_value(
                "knowledge.dialogue", "max_scopes_per_request", default=3
            ),
            logger=logger,
        )

    @staticmethod
    def validate_config(config_mgr: Any) -> None:
        """Reject obsolete security settings even when dialogue RAG is disabled."""
        section_reader = getattr(config_mgr, "section_dict", None)
        if callable(section_reader):
            obsolete_present = "user_scope_allowlist_json" in section_reader(
                "knowledge.dialogue"
            )
        else:
            missing = object()
            obsolete_present = (
                config_mgr.config_value(
                    "knowledge.dialogue",
                    "user_scope_allowlist_json",
                    default=missing,
                )
                is not missing
            )
        if obsolete_present:
            raise KnowledgeScopeConfigurationError(
                "knowledge.dialogue.user_scope_allowlist_json is obsolete; "
                "administer RAG usage privileges in Oracle."
            )

    def validate_startup(self) -> KnowledgeScopeResolution:
        """Validate all configured grants and aliases against current registries."""
        try:
            active = self._active_scopes(force_refresh=True)
        except KnowledgeScopeRegistryError:
            return KnowledgeScopeResolution("unavailable", "scope_registry_unavailable")
        configured = set(self._aliases.values())
        invalid = configured - active
        if invalid:
            self._log_warning(
                "Knowledge dialogue configuration references unknown or inactive "
                "scopes: "
                + ", ".join(sorted(scope.canonical_name for scope in invalid))
            )
            return KnowledgeScopeResolution("degraded", "configured_scope_inactive")
        if self._allow_all_scopes:
            self._log_warning(
                "SECURITY WARNING: rag_usage_allow_all_scopes is enabled; "
                "database privilege rows are bypassed for authenticated active users only."
            )
        return KnowledgeScopeResolution("ready", "scope_configuration_valid")

    def resolve_for_user(
        self,
        username: str,
        requested_names: tuple[str, ...],
    ) -> KnowledgeScopeResolution:
        """Resolve requested aliases/canonical names and enforce current user grants."""
        canonical_user = str(username or "").strip()
        if not canonical_user:
            return KnowledgeScopeResolution("denied", "RAG_USAGE_PRINCIPAL_UNKNOWN")
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

        bypassed = False
        for scope in resolved:
            try:
                result = self._authorization_repository.authorization_result(
                    canonical_user, scope
                )
            except KnowledgeScopeRegistryError:
                return KnowledgeScopeResolution(
                    "unavailable", "RAG_USAGE_AUTHORIZATION_UNAVAILABLE"
                )
            if result == "RAG_USAGE_GRANTED":
                continue
            if self._allow_all_scopes and result in {
                "RAG_USAGE_NOT_GRANTED",
                "RAG_USAGE_EXPIRED",
            }:
                bypassed = True
                continue
            if result in {
                "RAG_USAGE_SCOPE_INACTIVE",
                "RAG_USAGE_SCOPE_INELIGIBLE",
                "RAG_USAGE_AUTHORIZATION_UNAVAILABLE",
            }:
                return KnowledgeScopeResolution("inactive", result)
            if result == "RAG_USAGE_SCOPE_UNKNOWN":
                return KnowledgeScopeResolution("unknown", result)
            return KnowledgeScopeResolution("denied", result)
        try:
            active = self._active_scopes()
        except KnowledgeScopeRegistryError:
            return KnowledgeScopeResolution("unavailable", "scope_registry_unavailable")
        if any(scope not in active for scope in resolved):
            return KnowledgeScopeResolution("inactive", "knowledge_scope_inactive")
        return KnowledgeScopeResolution(
            "authorised",
            "rag_usage_allow_all_scopes" if bypassed else "RAG_USAGE_GRANTED",
            tuple(resolved),
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
