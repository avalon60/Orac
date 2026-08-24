"""Tests for authorised bounded knowledge content materialisation."""

# Author: Clive Bostock
# Date: 13-Aug-2026
# Description: Verifies controlled identities, provenance, limits, and managed-store checks.

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge import KnowledgeManagedStore  # noqa: E402
from orac_core.knowledge import KnowledgeMaterialisationRequest  # noqa: E402
from orac_core.knowledge import KnowledgeMaterialisationService  # noqa: E402
from orac_core.knowledge import KnowledgeScope  # noqa: E402


class _Repository:
    def __init__(self, rows, *, status="APPROVED", reason="RETRIEVAL_APPROVED"):
        self.rows = rows
        self.status = status
        self.reason = reason
        self.requests = []
        self.outcomes = []

    def resolve_request(self, **kwargs):
        self.requests.append(kwargs)
        return {"status": self.status, "reason_code": self.reason}, list(self.rows)

    def record_outcome(self, **kwargs):
        self.outcomes.append(kwargs)


def _member_row(write_result, **overrides):
    row = {
        "document_id": 10,
        "document_title": "Fixture",
        "document_version_id": 20,
        "revision_content_sha256": "b" * 64,
        "revision_mime_type": "application/pdf",
        "revision_byte_size": 999,
        "original_filename": "fixture.pdf",
        "source_format_code": "PDF",
        "extraction_id": 30,
        "normalised_text_sha256": write_result.identity.sha256,
        "output_mime_type": "text/markdown; charset=utf-8",
        "extractor_code": "fixture",
        "extractor_version": "1",
        "artefact_id": 40,
        "artefact_role_code": "PRIMARY",
        "artefact_media_type": "text/markdown; charset=utf-8",
        "artefact_content_sha256": write_result.identity.sha256,
        "artefact_storage_key": write_result.storage_key,
        "artefact_byte_size": write_result.identity.byte_size,
        "artefact_logical_name": "primary.md",
        "member_ordinal": 1,
        "artefact_metadata_json": None,
    }
    row.update(overrides)
    return row


class KnowledgeMaterialisationTests(unittest.TestCase):
    """Exercise authorised metadata and content retrieval without paths."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = KnowledgeManagedStore(Path(self.temporary.name) / "content")
        self.scope = KnowledgeScope("PROJECT", "ORAC_CORE")

    def tearDown(self):
        self.temporary.cleanup()

    def test_complete_content_is_verified_and_locator_is_not_public(self):
        payload = "# Safe\n\nNormalised evidence.\n".encode()
        write = self.store.put_bytes(payload)
        repository = _Repository([_member_row(write)])
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=repository
        )
        request = KnowledgeMaterialisationRequest(
            operation="CONTENT", target_type="ARTEFACT", target_id=40
        )

        with service.open_content(
            request, principal_username="clive", scope=self.scope
        ) as stream:
            returned = b"".join(stream.iter_bytes())
            public = repr(stream.result)

        self.assertEqual(returned, payload)
        self.assertNotIn(write.storage_key, public)
        self.assertNotIn(str(self.store.managed_root), public)
        self.assertEqual(stream.result.verification[0]["status"], "VERIFIED")
        self.assertEqual(repository.outcomes[-1]["outcome_code"], "COMPLETED")

    def test_cancelled_stream_audits_only_bytes_actually_yielded(self):
        payload = b"abcdefgh"
        write = self.store.put_bytes(payload)
        repository = _Repository([_member_row(write)])
        service = KnowledgeMaterialisationService(
            managed_store=self.store,
            repository=repository,
            block_size=4,
        )

        with service.open_content(
            KnowledgeMaterialisationRequest(
                operation="CONTENT", target_type="ARTEFACT", target_id=40
            ),
            principal_username="clive",
            scope=self.scope,
        ) as stream:
            first_block = next(stream.iter_bytes())

        self.assertEqual(first_block, b"abcd")
        self.assertEqual(repository.outcomes[-1]["outcome_code"], "CANCELLED")
        self.assertEqual(repository.outcomes[-1]["returned_byte_size"], 4)
        self.assertEqual(
            repository.outcomes[-1]["returned_sha256"],
            hashlib.sha256(b"abcd").hexdigest(),
        )

    def test_metadata_does_not_return_internal_locator(self):
        write = self.store.put_bytes(b"metadata")
        repository = _Repository([_member_row(write)])
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=repository
        )
        result = service.describe(
            KnowledgeMaterialisationRequest(
                operation="METADATA",
                target_type="DOCUMENT_VERSION",
                target_id=20,
                include_raw_metadata=True,
            ),
            principal_username="clive",
            scope=self.scope,
        )

        self.assertEqual(result.status, "COMPLETED")
        self.assertNotIn(write.storage_key, repr(result))
        self.assertEqual(result.members[0]["raw_metadata"]["original_filename"], "fixture.pdf")

    def test_denial_returns_no_rows_or_content(self):
        repository = _Repository(
            [], status="REJECTED", reason="RETRIEVAL_NOT_AUTHORISED"
        )
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=repository
        )
        with service.open_content(
            KnowledgeMaterialisationRequest(
                operation="CONTENT", target_type="DOCUMENT", target_id=10
            ),
            principal_username="clive",
            scope=self.scope,
        ) as stream:
            self.assertEqual(list(stream.iter_bytes()), [])
            self.assertEqual(stream.result.reason_code, "RETRIEVAL_NOT_AUTHORISED")
        self.assertEqual(repository.outcomes, [])

    def test_text_range_uses_unicode_code_points(self):
        write = self.store.put_bytes("Aé🙂Z".encode("utf-8"))
        repository = _Repository([_member_row(write)])
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=repository
        )
        request = KnowledgeMaterialisationRequest(
            operation="CONTENT",
            target_type="ARTEFACT",
            target_id=40,
            selection_type="TEXT_RANGE",
            selection={"artefact_id": 40, "start_char": 1, "end_char": 3},
        )
        with service.open_content(
            request, principal_username="clive", scope=self.scope
        ) as stream:
            self.assertEqual(b"".join(stream.iter_bytes()), "é🙂".encode())

    def test_table_range_is_bounded_by_registered_member_range(self):
        write = self.store.put_bytes(b"a,b,c\n1,2,3\n4,5,6\n")
        row = _member_row(
            write,
            artefact_id=41,
            artefact_role_code="TABLE",
            artefact_media_type="text/csv; charset=utf-8",
            artefact_logical_name="sheet.csv",
            artefact_metadata_json=json.dumps(
                {"schema_version": 1, "sheet_name": "S", "source_cell_range": "A1:C3"}
            ),
        )
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=_Repository([row])
        )
        request = KnowledgeMaterialisationRequest(
            operation="CONTENT",
            target_type="ARTEFACT",
            target_id=41,
            selection_type="TABLE_RANGE",
            selection={"artefact_id": 41, "cell_range": "B2:C3"},
        )
        with service.open_content(
            request, principal_username="clive", scope=self.scope
        ) as stream:
            self.assertEqual(b"".join(stream.iter_bytes()), b"2,3\n5,6\n")

    def test_chunk_range_verifies_each_chunk_hash(self):
        rows = []
        for chunk_id, chunk_no, text in ((51, 1, "one"), (52, 2, "two")):
            rows.append(
                {
                    "document_id": 10,
                    "document_version_id": 20,
                    "extraction_id": 30,
                    "chunk_set_id": 50,
                    "chunk_id": chunk_id,
                    "chunk_no": chunk_no,
                    "span_start": (chunk_no - 1) * 3,
                    "span_end": chunk_no * 3,
                    "chunk_text": text,
                    "chunk_content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
            )
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=_Repository(rows)
        )
        request = KnowledgeMaterialisationRequest(
            operation="CONTENT",
            target_type="CHUNK_SET",
            target_id=50,
            selection_type="CHUNK_RANGE",
            selection={"first_chunk_id": 51, "last_chunk_id": 52},
        )
        with service.open_content(
            request, principal_username="clive", scope=self.scope
        ) as stream:
            self.assertEqual(b"".join(stream.iter_bytes()), b"onetwo")
            self.assertEqual(len(stream.result.chunks), 2)

    def test_chunk_context_expands_anchors_within_returned_chunk_set(self):
        rows = []
        for chunk_id, chunk_no, text in (
            (51, 1, "one "),
            (52, 2, "two "),
            (53, 3, "three"),
        ):
            rows.append(
                {
                    "document_id": 10,
                    "document_version_id": 20,
                    "extraction_id": 30,
                    "chunk_set_id": 50,
                    "chunk_id": chunk_id,
                    "chunk_no": chunk_no,
                    "span_start": (chunk_no - 1) * 4,
                    "span_end": chunk_no * 4,
                    "chunk_text": text,
                    "chunk_content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "artefact_id": 40,
                }
            )
        write = self.store.put_bytes(b"one two three")
        for row in rows:
            row.update(_member_row(write, artefact_id=40))
            row["chunk_content_sha256"] = hashlib.sha256(
                row["chunk_text"].encode()
            ).hexdigest()
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=_Repository(rows)
        )
        request = KnowledgeMaterialisationRequest(
            operation="CONTENT",
            target_type="CHUNK_SET",
            target_id=50,
            selection_type="CHUNK_CONTEXT",
            selection={
                "first_anchor_chunk_id": 52,
                "last_anchor_chunk_id": 52,
                "context_before": 1,
                "context_after": 1,
            },
        )
        with service.open_content(
            request, principal_username="clive", scope=self.scope
        ) as stream:
            self.assertEqual(b"".join(stream.iter_bytes()), b"one two thre")
            self.assertEqual(stream.parts[0].provenance["first_chunk_id"], 51)
            self.assertEqual(stream.parts[0].provenance["last_chunk_id"], 53)

    def test_section_range_uses_verified_source_span(self):
        write = self.store.put_bytes(b"alpha beta gamma")
        rows = []
        for chunk_id, chunk_no, start, end in ((51, 1, 0, 5), (52, 2, 6, 10)):
            row = _member_row(write)
            row.update(
                {
                    "chunk_set_id": 50,
                    "chunk_id": chunk_id,
                    "chunk_no": chunk_no,
                    "span_start": start,
                    "span_end": end,
                    "chunk_text": "alpha" if chunk_no == 1 else "beta",
                    "chunk_content_sha256": hashlib.sha256(
                        ("alpha" if chunk_no == 1 else "beta").encode()
                    ).hexdigest(),
                }
            )
            rows.append(row)
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=_Repository(rows)
        )
        request = KnowledgeMaterialisationRequest(
            operation="CONTENT",
            target_type="CHUNK_SET",
            target_id=50,
            selection_type="SECTION_RANGE",
            selection={"first_chunk_id": 51, "last_chunk_id": 52},
        )
        with service.open_content(
            request, principal_username="clive", scope=self.scope
        ) as stream:
            self.assertEqual(b"".join(stream.iter_bytes()), b"alpha beta")
            self.assertEqual(stream.parts[0].provenance["section_span_end"], 10)

    def test_legacy_clob_has_explicit_null_artefact_provenance(self):
        text = "legacy normalised text"
        row = {
            "document_id": 10,
            "document_version_id": 20,
            "extraction_id": 30,
            "normalised_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "output_mime_type": "text/markdown; charset=utf-8",
            "legacy_extracted_text": text,
            "artefact_id": None,
        }
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=_Repository([row])
        )
        request = KnowledgeMaterialisationRequest(
            operation="CONTENT", target_type="EXTRACTION", target_id=30
        )
        with service.open_content(
            request, principal_username="clive", scope=self.scope
        ) as stream:
            self.assertEqual(b"".join(stream.iter_bytes()), text.encode())
            self.assertTrue(stream.result.members[0]["legacy_artefact_provenance"])
            self.assertEqual(
                stream.result.verification[0]["status"], "VERIFIED_CLOB_HASH"
            )

    def test_corrupt_registered_hash_fails_without_returning_bytes(self):
        write = self.store.put_bytes(b"safe")
        row = _member_row(write, artefact_content_sha256="f" * 64)
        repository = _Repository([row])
        service = KnowledgeMaterialisationService(
            managed_store=self.store, repository=repository
        )
        with service.open_content(
            KnowledgeMaterialisationRequest(
                operation="CONTENT", target_type="ARTEFACT", target_id=40
            ),
            principal_username="clive",
            scope=self.scope,
        ) as stream:
            self.assertEqual(list(stream.iter_bytes()), [])
            self.assertEqual(stream.result.reason_code, "RETRIEVAL_OBJECT_CORRUPT")
        self.assertEqual(repository.outcomes[-1]["outcome_code"], "FAILED")

    def test_missing_size_mismatch_symlink_and_traversal_fail_closed(self):
        cases = (
            ("missing", "RETRIEVAL_OBJECT_MISSING"),
            ("size", "RETRIEVAL_OBJECT_CORRUPT"),
            ("symlink", "RETRIEVAL_OBJECT_UNSAFE"),
            ("traversal", "RETRIEVAL_OBJECT_UNSAFE"),
        )
        for mutation, expected_reason in cases:
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory() as temporary:
                    base = Path(temporary)
                    store = KnowledgeManagedStore(base / "managed")
                    write = store.put_bytes(b"registered")
                    digest = write.identity.sha256
                    object_path = (
                        store.managed_root
                        / "sha256"
                        / digest[:2]
                        / digest[2:4]
                        / digest
                    )
                    row = _member_row(write)
                    if mutation == "missing":
                        object_path.unlink()
                    elif mutation == "size":
                        object_path.write_bytes(b"registered-extra")
                        object_path.chmod(0o600)
                    elif mutation == "symlink":
                        outside = base / "outside"
                        outside.write_bytes(b"registered")
                        object_path.unlink()
                        object_path.symlink_to(outside)
                    else:
                        row["artefact_storage_key"] = "../managed-object"
                    repository = _Repository([row])
                    service = KnowledgeMaterialisationService(
                        managed_store=store,
                        repository=repository,
                    )

                    with service.open_content(
                        KnowledgeMaterialisationRequest(
                            operation="CONTENT",
                            target_type="ARTEFACT",
                            target_id=40,
                        ),
                        principal_username="clive",
                        scope=self.scope,
                    ) as stream:
                        self.assertEqual(list(stream.iter_bytes()), [])
                        self.assertEqual(stream.result.reason_code, expected_reason)
                    self.assertEqual(
                        repository.outcomes[-1]["outcome_code"],
                        "FAILED",
                    )


if __name__ == "__main__":
    unittest.main()
