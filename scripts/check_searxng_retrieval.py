"""Check that SearXNG supports JSON search for Orac retrieval."""
# Author: Clive Bostock
# Date: 26-May-2026
# Description: Checks that the configured SearXNG instance supports JSON search for Orac retrieval.
# Purpose: Diagnose local SearXNG JSON API availability for explicit internet retrieval.
# Usage: poetry run python scripts/check_searxng_retrieval.py

from __future__ import annotations

import argparse
import configparser
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen


DEFAULT_QUERY = "Neil Armstrong"
DEFAULT_BASE_URL = "http://127.0.0.1:8888"


class SearXNGCheckError(Exception):
    """Raised when the SearXNG retrieval smoke check fails."""


def default_project_root() -> Path:
    """Return the project root inferred from this script location."""
    return Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(
        description="Check that the configured SearXNG instance returns JSON search results.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=default_project_root(),
        help="Project root. Default: inferred from script location.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="SearXNG base URL. Default: read from resources/config/orac.ini or use localhost:8888.",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help=f"Search query to test. Default: {DEFAULT_QUERY!r}.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="HTTP timeout in seconds. Default: read from config or use 10.",
    )
    return parser


def read_configured_searxng(root: Path) -> tuple[str, float]:
    """Read SearXNG settings from Orac's configuration file."""
    config_path = root / "resources" / "config" / "orac.ini"
    parser = configparser.ConfigParser()
    parser.read(config_path)

    base_url = DEFAULT_BASE_URL
    timeout = 10.0
    if parser.has_section("retrieval.searxng"):
        base_url = parser.get(
            "retrieval.searxng",
            "base_url",
            fallback=base_url,
        )
        timeout = parser.getfloat(
            "retrieval.searxng",
            "timeout_seconds",
            fallback=timeout,
        )
    return base_url.strip().rstrip("/"), max(0.1, timeout)


def search_url(base_url: str, query: str) -> str:
    """Build the SearXNG JSON search URL."""
    return f"{base_url.rstrip('/')}/search?{urlencode({'q': query, 'format': 'json'})}"


def fetch_search_payload(url: str, *, timeout: float) -> tuple[int, str, bytes]:
    """Fetch a SearXNG JSON search response."""
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Orac/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            content_type = str(response.headers.get("Content-Type", ""))
            body = response.read()
            return status, content_type, body
    except HTTPError as exc:
        body = exc.read()
        content_type = str(exc.headers.get("Content-Type", "")) if exc.headers else ""
        return int(exc.code), content_type, body
    except (TimeoutError, URLError, OSError) as exc:
        raise SearXNGCheckError(f"connection failed: {exc}") from exc


def validate_search_payload(
    *,
    status: int,
    content_type: str,
    body: bytes,
) -> dict:
    """Validate and return a SearXNG JSON payload."""
    if status != 200:
        preview = body.decode("utf-8", errors="replace")[:120].strip()
        raise SearXNGCheckError(f"HTTP status was {status}: {preview}")

    text = body.decode("utf-8", errors="replace").lstrip()
    if text.startswith("<"):
        raise SearXNGCheckError(
            "response was HTML, not JSON; check that search.formats includes json",
        )

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SearXNGCheckError(f"response was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SearXNGCheckError("top-level JSON payload was not an object")
    results = payload.get("results")
    if not isinstance(results, list):
        raise SearXNGCheckError("top-level JSON payload did not contain a results list")
    return payload


def run_check(*, base_url: str, query: str, timeout: float) -> int:
    """Run the SearXNG retrieval check and return an exit code."""
    url = search_url(base_url, query)
    try:
        status, content_type, body = fetch_search_payload(url, timeout=timeout)
        payload = validate_search_payload(
            status=status,
            content_type=content_type,
            body=body,
        )
    except SearXNGCheckError as exc:
        print(f"searxng retrieval check failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"searxng retrieval check passed: query={query!r} results={len(payload['results'])}",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the command-line smoke check."""
    args = build_parser().parse_args(argv)
    configured_base_url, configured_timeout = read_configured_searxng(args.root)
    base_url = (args.base_url or configured_base_url or DEFAULT_BASE_URL).strip().rstrip("/")
    timeout = max(0.1, float(args.timeout or configured_timeout))
    return run_check(base_url=base_url, query=args.query, timeout=timeout)


if __name__ == "__main__":
    raise SystemExit(main())
