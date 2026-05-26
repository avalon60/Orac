"""Conservative source fetching for explicit retrieval."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Fetches top search results and extracts readable evidence text.

from __future__ import annotations

from datetime import datetime
from datetime import timezone
from html import unescape
from html.parser import HTMLParser
from http.client import HTTPResponse
from ipaddress import ip_address as parse_ip_address
from typing import Any
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler
from urllib.request import build_opener
from urllib.request import Request
import re
import socket

from .models import FetchedSource
from .models import SearchResult


_ALLOWED_CONTENT_TYPES = {"text/html", "text/plain", "application/xhtml+xml"}
_METADATA_SERVICE_IPS = {"169.254.169.254"}
_REDIRECT_CODES = {301, 302, 303, 307, 308}


class SourceFetcher:
    """Fetches source pages conservatively and treats all content as untrusted."""

    def __init__(
        self,
        *,
        logger: Any,
        timeout_seconds: float = 5.0,
        max_sources_to_fetch: int = 3,
        max_bytes: int = 256_000,
        max_text_chars: int = 8_000,
        max_excerpt_chars: int = 900,
        max_redirects: int = 3,
    ) -> None:
        """Initialise the source fetcher."""
        self._logger = logger
        self._timeout_seconds = max(0.1, float(timeout_seconds))
        self._max_sources_to_fetch = max(1, int(max_sources_to_fetch))
        self._max_bytes = max(1, int(max_bytes))
        self._max_text_chars = max(256, int(max_text_chars))
        self._max_excerpt_chars = max(120, int(max_excerpt_chars))
        self._max_redirects = max(0, int(max_redirects))
        self._opener = build_opener(_NoRedirectHandler)

    def fetch_sources(
        self,
        results: tuple[SearchResult, ...] | list[SearchResult],
        *,
        max_sources: int | None = None,
    ) -> tuple[FetchedSource, ...]:
        """Fetch the top search result URLs and return readable source text."""
        limit = max_sources or self._max_sources_to_fetch
        fetched: list[FetchedSource] = []
        seen_urls: set[str] = set()

        for result in list(results)[:limit]:
            url = str(result.url or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            source = self._fetch_single_source(result)
            if source is not None:
                fetched.append(source)
        return tuple(fetched)

    def _fetch_single_source(self, result: SearchResult) -> FetchedSource | None:
        """Fetch one source URL and extract conservative readable text."""
        initial_url = str(result.url or "").strip()
        safety_error = _validate_fetch_url(initial_url)
        if safety_error is not None:
            self._log_warning(f"Blocked unsafe retrieval URL '{initial_url}': {safety_error}")
            return self._failure_source(
                result,
                initial_url,
                fetch_status="blocked_url",
                error_message=safety_error,
            )

        current_url = initial_url
        try:
            response = self._open_following_safe_redirects(current_url)
            with response:
                final_url = getattr(response, "url", current_url) or current_url
                safety_error = _validate_fetch_url(final_url)
                if safety_error is not None:
                    self._log_warning(f"Blocked unsafe retrieval redirect target '{final_url}': {safety_error}")
                    return self._failure_source(
                        result,
                        final_url,
                        fetch_status="blocked_url",
                        error_message=safety_error,
                    )
                raw_bytes = response.read(self._max_bytes + 1)
                content_type = self._content_type(response)
                charset = self._charset(response)
        except ValueError as exc:
            self._log_warning(f"Fetch blocked for '{result.url}': {exc}")
            return self._failure_source(
                result,
                initial_url,
                fetch_status="blocked_url" if _looks_like_safety_error(str(exc)) else "fetch_failed",
                error_message=str(exc),
            )
        except (HTTPError, URLError, TimeoutError) as exc:
            self._log_warning(f"Fetch failed for '{result.url}': {exc}")
            return self._failure_source(
                result,
                initial_url,
                fetch_status="fetch_failed",
                error_message=str(exc),
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            self._log_warning(f"Fetch failed for '{result.url}': {exc}")
            return self._failure_source(
                result,
                initial_url,
                fetch_status="fetch_failed",
                error_message=str(exc),
            )

        if content_type not in _ALLOWED_CONTENT_TYPES:
            message = f"unsupported content type: {content_type or 'unknown'}"
            self._log_warning(f"Skipping '{result.url}': {message}")
            return self._failure_source(
                result,
                initial_url,
                content_type=content_type,
                fetch_status="unsupported_content_type",
                error_message=message,
                byte_count=len(raw_bytes[: self._max_bytes]),
            )

        truncated = len(raw_bytes) > self._max_bytes
        raw_bytes = raw_bytes[: self._max_bytes]
        decoded = raw_bytes.decode(charset, errors="replace")
        text = self._extract_text(decoded, content_type=content_type)
        text = _normalize_whitespace(text)
        if truncated:
            text = f"{text} …" if text else "…"
        text = text[: self._max_text_chars]
        excerpt = self._select_excerpt(text)
        return FetchedSource(
            url=result.url,
            title=result.title,
            source_name=result.source_name,
            fetched_at=datetime.now(timezone.utc),
            content_type=content_type,
            text=text,
            excerpt=excerpt,
            byte_count=len(raw_bytes),
            source_rank=result.rank,
            fetch_status="truncated" if truncated else "ok",
        )

    def _open_following_safe_redirects(self, initial_url: str) -> HTTPResponse:
        """Open a URL while validating every redirect target before following."""
        current_url = initial_url
        for _ in range(self._max_redirects + 1):
            safety_error = _validate_fetch_url(current_url)
            if safety_error is not None:
                raise ValueError(safety_error)
            request = Request(
                current_url,
                headers={
                    "User-Agent": "Orac/1.0 (+https://github.com/openai/openai)",
                    "Accept": "text/html,application/xhtml+xml,text/plain",
                },
                method="GET",
            )
            try:
                return self._opener.open(request, timeout=self._timeout_seconds)
            except HTTPError as exc:
                if exc.code not in _REDIRECT_CODES:
                    raise
                location = exc.headers.get("Location") if exc.headers is not None else None
                if not location:
                    raise ValueError("redirect response did not include a location")
                redirected_url = urljoin(current_url, str(location))
                safety_error = _validate_fetch_url(redirected_url)
                if safety_error is not None:
                    raise ValueError(f"unsafe redirect target: {safety_error}")
                current_url = redirected_url
        raise ValueError("maximum redirect count exceeded")

    def _failure_source(
        self,
        result: SearchResult,
        url: str,
        *,
        fetch_status: str,
        error_message: str,
        content_type: str | None = None,
        byte_count: int | None = None,
    ) -> FetchedSource:
        """Return a structured fetch failure without exposing unsafe content."""
        return FetchedSource(
            url=url,
            title=result.title,
            source_name=result.source_name,
            fetched_at=datetime.now(timezone.utc),
            content_type=content_type,
            byte_count=byte_count,
            source_rank=result.rank,
            fetch_status=fetch_status,
            fetch_error=error_message,
            error_message=error_message,
        )

    def _extract_text(self, html_text: str, *, content_type: str | None) -> str:
        """Extract readable text from a response body conservatively."""
        if content_type:
            lowered = content_type.lower()
            if lowered.startswith("text/") and not lowered.startswith("text/html"):
                return html_text
            if lowered not in _ALLOWED_CONTENT_TYPES:
                return ""
        if "<html" not in html_text.lower() and "<body" not in html_text.lower():
            return html_text

        parser = _ReadableTextExtractor()
        parser.feed(html_text)
        parser.close()
        return parser.text()

    def _select_excerpt(self, text: str) -> str:
        """Return a compact excerpt suitable for prompt evidence."""
        if not text:
            return ""
        if len(text) <= self._max_excerpt_chars:
            return text
        return text[: self._max_excerpt_chars].rstrip() + " …"

    def _content_type(self, response: Any) -> str | None:
        """Return the response content type if available."""
        headers = getattr(response, "headers", None)
        if headers is None:
            return None
        get_content_type = getattr(headers, "get_content_type", None)
        if callable(get_content_type):
            try:
                return str(get_content_type() or "").strip() or None
            except Exception:
                pass
        value = headers.get("Content-Type") if hasattr(headers, "get") else None
        if not value:
            return None
        return str(value).split(";", 1)[0].strip() or None

    def _charset(self, response: Any) -> str:
        """Return the response charset or utf-8."""
        headers = getattr(response, "headers", None)
        if headers is None:
            return "utf-8"
        get_content_charset = getattr(headers, "get_content_charset", None)
        if callable(get_content_charset):
            try:
                charset = get_content_charset()
                if charset:
                    return str(charset)
            except Exception:
                pass
        return "utf-8"

    def _log_warning(self, message: str) -> None:
        """Log a safe warning if a logger is available."""
        log_warning = getattr(self._logger, "log_warning", None)
        if callable(log_warning):
            log_warning(message)


class _ReadableTextExtractor(HTMLParser):
    """Extracts plain text from HTML while skipping non-content elements."""

    _BLOCK_TAGS = {
        "article",
        "div",
        "li",
        "p",
        "section",
        "tr",
        "ul",
        "ol",
        "br",
        "hr",
        "header",
        "footer",
        "main",
        "aside",
        "nav",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "iframe"}

    def __init__(self) -> None:
        """Initialise the extractor."""
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        """Record structural boundaries and skip non-content tags."""
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        """Close skipped sections and preserve block boundaries."""
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        """Collect visible text."""
        if self._skip_depth > 0:
            return
        text = unescape(str(data or "")).strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        """Return the accumulated plain text."""
        return _normalize_whitespace(" ".join(self._parts))


def _normalize_whitespace(value: str) -> str:
    """Collapse whitespace and strip a value."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


class _NoRedirectHandler(HTTPRedirectHandler):
    """Prevent urllib from following redirects without caller validation."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        """Return None so redirects surface as HTTPError responses."""
        return None


def _validate_fetch_url(url: str) -> str | None:
    """Return an error message if a URL is unsafe for server-side fetching."""
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        return "only http and https URLs are allowed"
    hostname = parsed.hostname
    if not hostname:
        return "URL hostname is missing"
    lowered_hostname = hostname.strip().lower().rstrip(".")
    if lowered_hostname in {"localhost", "localhost.localdomain"} or lowered_hostname.endswith(".localhost"):
        return "localhost hostnames are not allowed"

    try:
        addresses = [parse_ip_address(lowered_hostname)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(lowered_hostname, parsed.port or _default_port(parsed.scheme), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            return f"hostname could not be resolved: {exc}"
        addresses = []
        for info in infos:
            sockaddr = info[4]
            if not sockaddr:
                continue
            addresses.append(parse_ip_address(sockaddr[0]))
        if not addresses:
            return "hostname resolved to no addresses"

    for address in addresses:
        reason = _unsafe_ip_reason(address)
        if reason is not None:
            return reason
    return None


def _unsafe_ip_reason(address) -> str | None:
    """Return the reason an IP address is unsafe for retrieval."""
    if str(address) in _METADATA_SERVICE_IPS:
        return "metadata service addresses are not allowed"
    if address.is_loopback:
        return "loopback addresses are not allowed"
    if address.is_private:
        return "private addresses are not allowed"
    if address.is_link_local:
        return "link-local addresses are not allowed"
    if address.is_multicast:
        return "multicast addresses are not allowed"
    if address.is_reserved:
        return "reserved addresses are not allowed"
    if address.is_unspecified:
        return "unspecified addresses are not allowed"
    return None


def _default_port(scheme: str) -> int:
    """Return the default TCP port for a supported URL scheme."""
    return 443 if scheme.lower() == "https" else 80


def _looks_like_safety_error(message: str) -> bool:
    """Return whether a fetch failure came from URL safety validation."""
    lowered = str(message or "").lower()
    return any(
        token in lowered
        for token in (
            "not allowed",
            "unsafe redirect target",
            "hostname could not be resolved",
            "hostname resolved to no addresses",
            "url hostname is missing",
        )
    )
