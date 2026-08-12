"""Tests for Core knowledge repository Oracle value handling."""

# Author: Clive Bostock
# Date: 12-Aug-2026
# Description: Verifies session-safe materialisation of ingestion text CLOBs.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge.repository import KnowledgeIngestionRepository  # noqa: E402


class _ConnectionBoundLob:
    """Fake Oracle LOB that becomes unreadable after session closure."""

    def __init__(
        self,
        session: "_DetailSession",
        payload: object = "materialised extraction",
        *,
        error: Exception | None = None,
    ) -> None:
        self._session = session
        self._payload = payload
        self._error = error
        self.read_count = 0

    def read(self) -> object:
        """Read once while the owning session remains open."""
        if self._session.closed:
            raise RuntimeError("not connected to database")
        self.read_count += 1
        if self._error is not None:
            raise self._error
        return self._payload


class _DetailCursor:
    """Minimal ingestion-detail cursor."""

    description = [
        ("INGESTION_REQUEST_ID",),
        ("STATUS_CODE",),
        ("EXTRACTED_TEXT",),
    ]

    def __init__(self, session: "_DetailSession") -> None:
        self._session = session

    def __enter__(self) -> "_DetailCursor":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, statement: str, parameters: dict[str, int]) -> None:
        self.statement = statement
        self.parameters = parameters

    def fetchone(self) -> tuple[int, str, object] | None:
        return self._session.row


class _DetailSession:
    """Minimal session recording deterministic cleanup."""

    def __init__(self, extracted_text: object) -> None:
        self.closed = False
        self.row: tuple[int, str, object] | None = (1, "PROCESSING", extracted_text)

    def cursor(self) -> _DetailCursor:
        return _DetailCursor(self)

    def close(self) -> None:
        self.closed = True


class KnowledgeRepositoryTests(unittest.TestCase):
    """Tests ingestion detail text materialisation and cleanup."""

    def _repository(self, session: _DetailSession) -> KnowledgeIngestionRepository:
        return KnowledgeIngestionRepository(session_factory=lambda: session)

    def test_request_detail_reads_lob_once_before_session_closure(self) -> None:
        session = _DetailSession(None)
        lob = _ConnectionBoundLob(session)
        session.row = (1, "PROCESSING", lob)

        detail = self._repository(session).request_detail(1)

        self.assertEqual(detail["extracted_text"], "materialised extraction")
        self.assertEqual(lob.read_count, 1)
        self.assertTrue(session.closed)

    def test_request_detail_preserves_plain_string_and_null(self) -> None:
        for value in ("plain extraction", None):
            with self.subTest(value=value):
                session = _DetailSession(value)

                detail = self._repository(session).request_detail(1)

                self.assertIs(detail["extracted_text"], value)
                self.assertTrue(session.closed)

    def test_request_detail_rejects_non_text_lob_payload(self) -> None:
        session = _DetailSession(None)
        lob = _ConnectionBoundLob(session, b"binary payload")
        session.row = (1, "PROCESSING", lob)

        with self.assertRaisesRegex(TypeError, "extracted_text"):
            self._repository(session).request_detail(1)

        self.assertEqual(lob.read_count, 1)
        self.assertTrue(session.closed)

    def test_request_detail_closes_session_when_lob_read_fails(self) -> None:
        session = _DetailSession(None)
        lob = _ConnectionBoundLob(session, error=RuntimeError("LOB read failed"))
        session.row = (1, "PROCESSING", lob)

        with self.assertRaisesRegex(RuntimeError, "LOB read failed"):
            self._repository(session).request_detail(1)

        self.assertEqual(lob.read_count, 1)
        self.assertTrue(session.closed)

    def test_request_detail_closes_session_when_row_is_missing(self) -> None:
        session = _DetailSession(None)
        session.row = None

        with self.assertRaisesRegex(LookupError, "not found"):
            self._repository(session).request_detail(1)

        self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
