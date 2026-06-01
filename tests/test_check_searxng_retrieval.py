"""Tests for the SearXNG retrieval smoke-check script."""
# Author: Clive Bostock
# Date: 26-May-2026
# Description: Verifies SearXNG smoke-check response validation.

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_searxng_retrieval.py"

spec = importlib.util.spec_from_file_location(
    "check_searxng_retrieval",
    SCRIPT_PATH,
)
check_searxng_retrieval = importlib.util.module_from_spec(spec)
assert spec is not None
assert spec.loader is not None
spec.loader.exec_module(check_searxng_retrieval)


class CheckSearXngRetrievalTests(unittest.TestCase):
    """Unit tests for SearXNG smoke-check validation."""

    def test_html_403_is_rejected(self) -> None:
        """HTML error pages should fail as non-JSON responses."""
        body = b"<!doctype html><title>403 Forbidden</title>"

        with self.assertRaises(check_searxng_retrieval.SearXNGCheckError) as ctx:
            check_searxng_retrieval.validate_search_payload(
                status=403,
                content_type="text/html",
                body=body,
            )

        self.assertIn("HTTP status was 403", str(ctx.exception))

    def test_html_200_is_rejected(self) -> None:
        """HTML success pages should fail because Orac needs JSON."""
        body = b"<!doctype html><title>SearXNG</title>"

        with self.assertRaises(check_searxng_retrieval.SearXNGCheckError) as ctx:
            check_searxng_retrieval.validate_search_payload(
                status=200,
                content_type="text/html",
                body=body,
            )

        self.assertIn("response was HTML", str(ctx.exception))

    def test_valid_json_is_accepted(self) -> None:
        """A normal SearXNG JSON payload should be accepted."""
        payload = check_searxng_retrieval.validate_search_payload(
            status=200,
            content_type="application/json",
            body=b'{"query": "Neil Armstrong", "results": [{"title": "Neil"}]}',
        )

        self.assertEqual(payload["query"], "Neil Armstrong")
        self.assertEqual(len(payload["results"]), 1)


if __name__ == "__main__":
    unittest.main()
