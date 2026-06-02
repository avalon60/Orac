"""Search provider abstractions and the SearXNG implementation."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Defines provider-neutral search access and a SearXNG adapter.

from __future__ import annotations

from typing import Any
from typing import Protocol
from typing import runtime_checkable
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen
import json

from .models import SearchRequest
from .models import SearchResult


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol for provider-neutral search providers."""

    name: str

    def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Return structured search results for the given request."""


class SearXNGSearchProvider:
    """Search provider for a configured SearXNG instance."""

    name = "searxng"

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 10.0,
        logger: Any | None = None,
    ) -> None:
        """Initialise the provider."""
        self._base_url = str(base_url or "").strip().rstrip("/")
        self._timeout_seconds = max(0.1, float(timeout_seconds))
        self._logger = logger

    def search(self, request: SearchRequest) -> tuple[SearchResult, ...]:
        """Return structured results from the SearXNG JSON search endpoint."""
        if not request.query.strip():
            return ()
        if not self._base_url:
            self._log_warning("SearXNG base URL is not configured.")
            return ()

        params = {"q": request.query, "format": "json"}
        search_url = f"{self._base_url}/search?{urlencode(params)}"
        http_request = Request(
            search_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Orac/1.0 (+https://github.com/openai/openai)",
                "X-Forwarded-For": "127.0.0.1",
                "X-Real-IP": "127.0.0.1",
            },
            method="GET",
        )

        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:
                raw_bytes = response.read()
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            self._log_warning(f"SearXNG search failed for '{request.query}': {exc}")
            return ()
        except Exception as exc:  # pragma: no cover - defensive fallback
            self._log_warning(f"SearXNG search failed for '{request.query}': {exc}")
            return ()

        try:
            payload = json.loads(raw_bytes.decode("utf-8", errors="replace"))
        except Exception as exc:
            self._log_warning(f"SearXNG returned malformed JSON for '{request.query}': {exc}")
            return ()

        result_items = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(result_items, list):
            return ()

        results: list[SearchResult] = []
        for index, item in enumerate(result_items, start=1):
            if not isinstance(item, dict):
                continue
            url = _first_nonempty(item, ("url", "link", "href"))
            if not url:
                continue
            title = _first_nonempty(item, ("title", "name")) or url
            snippet = _first_nonempty(item, ("content", "snippet", "description"))
            engine = _first_nonempty(item, ("engine", "source"))
            source_name = engine or _host_from_url(url)
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    content=_first_nonempty(item, ("content", "snippet", "description")),
                    source_name=source_name,
                    engine=engine,
                    rank=index,
                    metadata=dict(item),
                )
            )
            if len(results) >= max(1, int(request.max_results)):
                break
        return tuple(results)

    def _log_warning(self, message: str) -> None:
        """Log a safe warning if a logger is available."""
        if self._logger is None:
            return
        log_warning = getattr(self._logger, "log_warning", None)
        if callable(log_warning):
            log_warning(message)


def _first_nonempty(item: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Return the first non-empty string from a mapping."""
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _host_from_url(url: str) -> str | None:
    """Return a stable source label from a URL."""
    parsed = urlparse(str(url or "").strip())
    return parsed.netloc or None
