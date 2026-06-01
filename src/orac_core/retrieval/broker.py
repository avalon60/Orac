"""Search broker configuration and provider selection."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Reads retrieval config, selects a provider, and limits results.

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from time import time
from typing import Any
from typing import Mapping

from .models import SearchRequest
from .models import SearchResult
from .providers import SearchProvider


@dataclass(frozen=True, slots=True)
class RetrievalSettings:
    """Runtime settings for explicit internet retrieval."""

    internet_search_enabled: bool = False
    internet_search_mode: str = "explicit_only"
    default_search_provider: str = "searxng"
    max_search_results: int = 5
    max_sources_to_fetch: int = 3
    cache_ttl_hours: float = 12.0
    require_citations: bool = True


class SearchBroker:
    """Selects a search provider and returns structured search results."""

    def __init__(
        self,
        *,
        logger: Any,
        providers: Mapping[str, SearchProvider] | None = None,
        settings: RetrievalSettings | None = None,
        config_mgr: Any | None = None,
    ) -> None:
        """Initialise the broker from explicit settings or the Orac config."""
        self._logger = logger
        self._providers = {str(name).strip().lower(): provider for name, provider in (providers or {}).items()}
        self._cache: dict[tuple[str, str], tuple[float, tuple[SearchResult, ...]]] = {}
        self._settings = settings or self._load_settings(config_mgr)

    @property
    def settings(self) -> RetrievalSettings:
        """Return the broker settings."""
        return self._settings

    def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Return structured results for a single search request."""
        if not self._settings.internet_search_enabled:
            self._log_debug("Internet search is disabled.")
            return ()

        query = " ".join(str(request.query or "").split())
        if not query:
            return ()

        provider_name = (
            str(request.provider_name or self._settings.default_search_provider or "")
            .strip()
            .lower()
        )
        if not provider_name:
            self._log_warning("No search provider is configured.")
            return ()

        provider = self._providers.get(provider_name)
        if provider is None:
            self._log_warning(f"Search provider '{provider_name}' is not available.")
            return ()

        effective_max = max(
            1,
            min(int(request.max_results or self._settings.max_search_results), self._settings.max_search_results),
        )
        cache_key = (provider_name, query.lower())
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached_at, cached_results = cached
            if time() - cached_at <= max(0.0, float(self._settings.cache_ttl_hours)) * 3600.0:
                return cached_results[:effective_max]

        provider_request = replace(
            request,
            query=query,
            max_results=effective_max,
            provider_name=provider_name,
        )
        try:
            results = tuple(provider.search(provider_request))
        except Exception as exc:  # pragma: no cover - defensive provider isolation
            self._log_warning(f"Search provider '{provider_name}' failed: {exc}")
            return ()

        if not results:
            return ()

        limited = results[:effective_max]
        self._cache[cache_key] = (time(), limited)
        return limited

    @property
    def max_sources_to_fetch(self) -> int:
        """Return the configured source fetch limit."""
        return max(1, int(self._settings.max_sources_to_fetch))

    def _load_settings(self, config_mgr: Any | None) -> RetrievalSettings:
        """Read retrieval settings from the existing Orac config manager."""
        if config_mgr is None:
            return RetrievalSettings()

        try:
            return RetrievalSettings(
                internet_search_enabled=_bool_config_value(
                    config_mgr,
                    "retrieval",
                    "internet_search_enabled",
                    default=False,
                ),
                internet_search_mode=str(
                    _config_value(
                        config_mgr,
                        "retrieval",
                        "internet_search_mode",
                        default="explicit_only",
                    )
                ).strip().lower()
                or "explicit_only",
                default_search_provider=str(
                    _config_value(
                        config_mgr,
                        "retrieval",
                        "default_search_provider",
                        default="searxng",
                    )
                ).strip().lower()
                or "searxng",
                max_search_results=max(
                    1,
                    int(
                        _int_config_value(
                            config_mgr,
                            "retrieval",
                            "max_search_results",
                            default=5,
                        )
                    ),
                ),
                max_sources_to_fetch=max(
                    1,
                    int(
                        _int_config_value(
                            config_mgr,
                            "retrieval",
                            "max_sources_to_fetch",
                            default=3,
                        )
                    ),
                ),
                cache_ttl_hours=max(
                    0.0,
                    float(
                        _float_config_value(
                            config_mgr,
                            "retrieval",
                            "cache_ttl_hours",
                            default=12.0,
                        )
                    ),
                ),
                require_citations=_bool_config_value(
                    config_mgr,
                    "retrieval",
                    "require_citations",
                    default=True,
                ),
            )
        except Exception:
            return RetrievalSettings()

    def _log_debug(self, message: str) -> None:
        """Log a debug message if possible."""
        log_debug = getattr(self._logger, "log_debug", None)
        if callable(log_debug):
            log_debug(message)

    def _log_warning(self, message: str) -> None:
        """Log a warning message if possible."""
        log_warning = getattr(self._logger, "log_warning", None)
        if callable(log_warning):
            log_warning(message)


def _config_value(config_mgr: Any, section: str, key: str, default: Any = None) -> Any:
    """Read a string config value from the existing config manager."""
    return config_mgr.config_value(section, key, default=default)


def _bool_config_value(config_mgr: Any, section: str, key: str, default: bool = False) -> bool:
    """Read a boolean config value from the existing config manager."""
    return config_mgr.bool_config_value(section, key, default=default)


def _int_config_value(config_mgr: Any, section: str, key: str, default: int = 0) -> int:
    """Read an integer config value from the existing config manager."""
    return config_mgr.int_config_value(section, key, default=default)


def _float_config_value(config_mgr: Any, section: str, key: str, default: float = 0.0) -> float:
    """Read a float config value from the existing config manager."""
    return config_mgr.float_config_value(section, key, default=default)
