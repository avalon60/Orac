"""Tests for the Core knowledge ingestion worker."""
# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Verifies scheduled worker health and stale-error behaviour.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge.worker import KnowledgeIngestionService


class _IdleRepository:
    def try_claim_next_request(self, *, owner_id: str, lease_seconds: int) -> None:
        del owner_id, lease_seconds
        return None


class KnowledgeIngestionWorkerTests(unittest.TestCase):
    """Tests scheduled worker state transitions."""

    def test_idle_tick_clears_previous_error(self) -> None:
        service = KnowledgeIngestionService(repository=_IdleRepository())
        service.last_error = "previous package error"

        service.tick(object())

        self.assertIsNone(service.last_error)
        self.assertTrue(service.health(object()))


if __name__ == "__main__":
    unittest.main()
