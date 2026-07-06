"""Tests for the drop-box database repository boundary."""
# Author: Clive Bostock
# Date: 27-Jun-2026
# Description: Verifies ORAC_PLUGIN package calls and narrow runtime reads.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for path in (SRC_ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from drop_box.models import CandidateFile, DropLocation, FileObservation, HashedCandidate
from drop_box.repository import DropBoxRepository


class _FakeSession:
    def __init__(self) -> None:
        self.connected_username = "ORAC_PLUGIN"
        self.fetch_queries: list[str] = []
        self.function_calls: list[tuple] = []
        self.procedure_calls: list[tuple] = []
        self.rows = [
            {
                "DROP_LOCATION_ID": 1,
                "LOCATION_CODE": "TEST",
                "DISPLAY_NAME": "Test",
                "PATH": "/tmp/drop",
                "ALLOWED_EXTENSIONS": "md, txt",
                "RECURSIVE_YN": "Y",
                "MAX_FILE_SIZE_MB": 2,
                "STABILITY_SECONDS": 5,
                "IGNORE_PATTERNS": "*.tmp",
            }
        ]

    def fetch_dicts(self, sql_query: str, bind_vars=None) -> list[dict]:
        self.fetch_queries.append(sql_query)
        return self.rows

    def call_function(self, function_name: str, *, return_type, parameters=None, auto_commit=False):
        self.function_calls.append((function_name, list(parameters or [])))
        return 1

    def call_procedure(self, procedure_name: str, parameters=None, *, auto_commit=False):
        self.procedure_calls.append((procedure_name, list(parameters or [])))
        return list(parameters or [])

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeContext:
    def __init__(self, session: _FakeSession) -> None:
        self.session = session

    def plugin_db_session(self) -> _FakeSession:
        return self.session


class DropBoxRepositoryTests(unittest.TestCase):
    """Tests repository use of the plugin database bridge."""

    def test_load_enabled_locations_reads_runtime_view(self) -> None:
        session = _FakeSession()
        repository = DropBoxRepository(_FakeContext(session))

        locations = repository.load_enabled_locations()

        self.assertEqual(locations[0].drop_location_id, 1)
        self.assertEqual(locations[0].allowed_extensions, ("md", "txt"))
        self.assertTrue(locations[0].recursive)
        self.assertEqual(locations[0].max_file_size_bytes, 2 * 1024 * 1024)
        self.assertIn("orac_dropbox.drop_location_runtime_v", session.fetch_queries[0])

    def test_observation_exists_uses_package_function(self) -> None:
        session = _FakeSession()
        repository = DropBoxRepository(_FakeContext(session))
        candidate = _candidate()

        self.assertTrue(repository.observation_exists(candidate))

        self.assertEqual(session.function_calls[0][0], "orac_dropbox.drop_box_api.observation_exists")
        self.assertEqual(session.function_calls[0][1][0:3], [1, "/tmp/drop/source.md", 7])

    def test_enqueue_job_passes_only_observed_metadata_and_hash(self) -> None:
        session = _FakeSession()
        repository = DropBoxRepository(_FakeContext(session))
        candidate = _candidate()
        hashed = HashedCandidate(candidate=candidate, source_hash="a" * 64)

        repository.enqueue_job(hashed)

        procedure_name, parameters = session.procedure_calls[0]
        self.assertEqual(procedure_name, "orac_dropbox.drop_box_api.enqueue_job")
        self.assertEqual(parameters[0:4], [1, "/tmp/drop/source.md", "source.md", 7])
        self.assertEqual(parameters[-1], "a" * 64)
        self.assertNotIn("processing_instruction", repr(parameters).lower())
        self.assertNotIn("target_scope", repr(parameters).lower())

    def test_rejects_non_orac_plugin_identity(self) -> None:
        session = _FakeSession()
        session.connected_username = "ORAC_DROPBOX"

        with self.assertRaisesRegex(RuntimeError, "ORAC_PLUGIN"):
            DropBoxRepository(_FakeContext(session))


def _candidate() -> CandidateFile:
    observed_at = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
    location = DropLocation(
        drop_location_id=1,
        location_code="TEST",
        display_name="Test",
        path=Path("/tmp/drop"),
    )
    return CandidateFile(
        location=location,
        observation=FileObservation(
            path=Path("/tmp/drop/source.md"),
            size_bytes=7,
            mtime_ns=1_789_999_999_000_000_000,
            source_mtime=observed_at,
            observed_at=observed_at,
        ),
    )


if __name__ == "__main__":
    unittest.main()
