"""Verify the plugin APEX search worker and its database boundary."""
# Author: Clive Bostock
# Date: 25-Oct-2026
# Description: Tests bounded search references and session-bound SQL contracts.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orac_core.knowledge.apex_search import KnowledgeApexSearchService  # noqa: E402
from orac_core.knowledge.service_manifest import (  # noqa: E402
    core_knowledge_service_manifest,
)


@dataclass
class _FakeRepository:
    """Capture worker effects without a database connection."""

    request: dict | None
    completed: list | None = None
    failed: list | None = None
    purged: bool = False

    def __post_init__(self) -> None:
        self.completed = []
        self.failed = []

    def purge_expired(self) -> None:
        """Record expiry processing."""
        self.purged = True

    def claim_next(self, worker_id: str) -> dict | None:
        """Yield the configured request exactly once."""
        del worker_id
        request, self.request = self.request, None
        return request

    def complete(self, *args: object) -> None:
        """Record a completed request."""
        self.completed.append(args)

    def fail(self, *args: object, **kwargs: object) -> None:
        """Record a failed request."""
        self.failed.append((args, kwargs))


class KnowledgeApexSearchTests(unittest.TestCase):
    """Protect the search handoff and least-privilege SQL shape."""

    def test_worker_persists_only_bounded_result_identities(self) -> None:
        """The result queue must not persist retrieved passage text."""
        request = {
            "request_id": 12,
            "lease_token": "lease",
            "username": "Clive",
            "plugin_id": "chess",
            "query": "minority attack",
        }
        repository = _FakeRepository(request)
        item = SimpleNamespace(
            document_id=1, document_version_id=2, chunk_id=3,
            chunk_no=4, fused_score=0.75, chunk_text="private passage",
        )
        retrieval = SimpleNamespace(
            retrieve_for_plugin=lambda *args, **kwargs: SimpleNamespace(
                status="grounded", results=(item,)
            )
        )
        worker = KnowledgeApexSearchService(
            repository=repository, retrieval_service=retrieval
        )
        worker.tick(None)

        self.assertTrue(repository.purged)
        self.assertEqual(repository.failed, [])
        self.assertEqual(repository.completed[0][3], [{
            "document_id": 1, "document_version_id": 2,
            "chunk_id": 3, "chunk_no": 4, "relevance_score": 0.75,
        }])
        self.assertNotIn("private passage", repr(repository.completed))

    def test_worker_does_not_complete_failed_retrieval(self) -> None:
        """A failed retrieval cannot become an empty successful search."""
        repository = _FakeRepository({
            "request_id": 12, "lease_token": "lease",
            "username": "Clive", "plugin_id": "chess", "query": "test",
        })
        retrieval = SimpleNamespace(
            retrieve_for_plugin=lambda *args, **kwargs: SimpleNamespace(
                status="failed", results=()
            )
        )
        KnowledgeApexSearchService(
            repository=repository, retrieval_service=retrieval
        ).tick(None)

        self.assertEqual(repository.completed, [])
        self.assertEqual(repository.failed[0][1], {"retryable": False})

    def test_apex_package_derives_identity_and_has_narrow_grant(self) -> None:
        """SQLcl without APEX context cannot nominate a principal or scope."""
        spec = (ROOT / "resources/db/schema/orac_code/package_spec/"
                "knowledge_apex_search_api.sql").read_text()
        body = (ROOT / "resources/db/schema/orac_code/package_body/"
                "knowledge_apex_search_api.sql").read_text()
        grant = (ROOT / "resources/db/schema/orac_code/grant/"
                 "knowledge_apex_search_api_access.sql").read_text()
        worker_grant = (ROOT / "resources/db/schema/orac_code/grant/"
                        "knowledge_apex_search_worker_access.sql").read_text()

        self.assertIn("sys_context('APEX$SESSION', 'APP_USER')", body)
        self.assertIn("sys_context('APEX$SESSION', 'APP_ID')", body)
        self.assertIn("KNOWLEDGE_APEX_SESSION_REQUIRED", body)
        self.assertNotIn("p_username", spec)
        self.assertNotIn("p_plugin_id", spec)
        self.assertIn("to orac_apx_pub", grant)
        self.assertNotIn("to orac_apx_pub", worker_grant)

    def test_core_registers_search_worker_with_knowledge_service(self) -> None:
        """The queue has a supervised consumer when knowledge is enabled."""
        manifest = core_knowledge_service_manifest(include_knowledge=True)
        codes = {runtime.service_code for runtime in manifest.service_runtimes}
        self.assertIn("knowledge_apex_search", codes)
        self.assertIn("knowledge_ingestion", codes)
