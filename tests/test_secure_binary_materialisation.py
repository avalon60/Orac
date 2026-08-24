"""Tests for secure bounded P2-06 binary materialisation."""

# Author: Clive Bostock
# Date: 23-Aug-2026
# Description: Verifies fail-closed route, source, limit, handle, and recovery controls.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys
import tempfile
import time
import unittest
import uuid

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.knowledge import ApprovedProcessorProfile  # noqa: E402
from orac_core.knowledge import BinaryMaterialisationConfiguration  # noqa: E402
from orac_core.knowledge import BinaryMaterialisationRequest  # noqa: E402
from orac_core.knowledge import DeterministicDerivativeEvidence  # noqa: E402
from orac_core.knowledge import KnowledgeManagedStore  # noqa: E402
from orac_core.knowledge import KnowledgeScope  # noqa: E402
from orac_core.knowledge import LimitDimension  # noqa: E402
from orac_core.knowledge import LogicalBinarySelection  # noqa: E402
from orac_core.knowledge import MaterialisationLimit  # noqa: E402
from orac_core.knowledge import MediaSafetyEvidence  # noqa: E402
from orac_core.knowledge import MimeDecision  # noqa: E402
from orac_core.knowledge import P204PolicyApproval  # noqa: E402
from orac_core.knowledge import P205RouteApproval  # noqa: E402
from orac_core.knowledge import ProcessorInspection  # noqa: E402
from orac_core.knowledge import ProcessorProfileIdentity  # noqa: E402
from orac_core.knowledge import SecureBinaryMaterialisationService  # noqa: E402
from orac_core.knowledge import SelectionAxis  # noqa: E402
from orac_core.knowledge import SelectionCoordinate  # noqa: E402
from orac_core.knowledge.binary_materialisation import (  # noqa: E402
    BinaryMaterialisationDisposition,
)
from orac_core.knowledge.binary_materialisation import (  # noqa: E402
    CoreBinarySourceResolver,
)
from orac_core.knowledge.binary_materialisation import (  # noqa: E402
    P204Disposition,
)
from orac_core.knowledge.binary_materialisation import (  # noqa: E402
    P205Disposition,
)
from orac_core.knowledge.binary_materialisation import (  # noqa: E402
    P205RouteKind,
)
from orac_core.knowledge.binary_materialisation import (  # noqa: E402
    RouteRevalidation,
)
from orac_core.knowledge.binary_materialisation import (  # noqa: E402
    source_identity_fingerprint,
)


class _Repository:
    """Synthetic authorised Core retrieval package boundary."""

    def __init__(self, row: dict[str, object]) -> None:
        self.row = row
        self.status = "APPROVED"
        self.reason = "RETRIEVAL_APPROVED"
        self.requests: list[dict[str, object]] = []
        self.outcomes: list[dict[str, object]] = []

    def resolve_request(self, **kwargs):
        """Return one registered row without accessing a development database."""
        self.requests.append(kwargs)
        rows = [dict(self.row)] if self.status == "APPROVED" else []
        return {"status": self.status, "reason_code": self.reason}, rows

    def record_outcome(self, **kwargs):
        """Capture content-free outcomes for assertions."""
        self.outcomes.append(kwargs)


class _RouteRevalidator:
    """Exact synthetic positive route evidence for approved fixtures only."""

    def __init__(self, *, approved: bool = True) -> None:
        self.approved = approved
        self.calls = 0

    def revalidate(self, request, *, evaluated_at):
        """Return fingerprints from the exact immutable fixture request."""
        self.calls += 1
        return RouteRevalidation(
            approved=self.approved,
            reason_code=(
                "MAT_ROUTE_REVALIDATED"
                if self.approved
                else "MAT_ROUTE_REVALIDATOR_UNAVAILABLE"
            ),
            route_fingerprint=request.route.fingerprint,
            policy_fingerprint=request.policy.fingerprint,
            evaluated_at=evaluated_at,
        )


class _FixtureProcessor:
    """Bounded deterministic processor used only by isolated synthetic tests."""

    def __init__(
        self,
        identity: ProcessorProfileIdentity,
        *,
        measurements: tuple[MaterialisationLimit, ...],
        inspection_overrides: dict[str, object] | None = None,
        output: bytes = b"safe-selection",
        cancel_during_write: bool = False,
    ) -> None:
        self.identity = identity
        self.measurements = measurements
        self.inspection_overrides = inspection_overrides or {}
        self.output = output
        self.cancel_during_write = cancel_during_write
        self.materialise_calls = 0

    def inspect(self, source, *, selection, limits, check_terminal):
        """Inspect only a source whose registered byte size is already bounded."""
        del selection
        check_terminal()
        source.read(min(limits[LimitDimension.BYTES], 4096))
        values: dict[str, object] = {
            "verified_representation": "fixture_binary",
            "detected_mime_type": "application/x-orac-fixture",
            "mime_decision": MimeDecision.EXACT,
            "measurements": self.measurements,
            "signature_valid": True,
            "structure_valid": True,
        }
        values.update(self.inspection_overrides)
        return ProcessorInspection(**values)

    def materialise(self, source, sink, *, selection, limits, check_terminal):
        """Emit a fixed deterministic derivative through the bounded sink."""
        del source, selection, limits
        self.materialise_calls += 1
        check_terminal()
        midpoint = max(1, len(self.output) // 2)
        sink.write(self.output[:midpoint])
        if self.cancel_during_write:
            check_terminal()
        sink.write(self.output[midpoint:])
        return DeterministicDerivativeEvidence(
            derivative_id=str(uuid.uuid4()),
            output_representation="fixture_selection",
            processor=self.identity,
            authoritative=True,
            provenance_fingerprint=hashlib.sha256(
                b"deterministic-fixture-provenance"
            ).hexdigest(),
        )


class SecureBinaryMaterialisationTests(unittest.TestCase):
    """Prove P2-06 controls without a network, provider, or mutable database."""

    def setUp(self) -> None:
        """Create isolated managed and attachment roots."""
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = KnowledgeManagedStore(self.root / "managed")
        self.payload = b"synthetic approved binary fixture"
        self.write = self.store.put_bytes(self.payload)
        self.now = datetime.now(timezone.utc)
        self.identity = ProcessorProfileIdentity(
            processor_code="fixture_processor",
            profile_code="bounded_copy",
            version="1.0",
        )
        self.dimensions = (
            MaterialisationLimit(LimitDimension.BYTES, len(self.payload), "BYTES"),
            MaterialisationLimit(LimitDimension.OUTPUT_BYTES, 1024, "BYTES"),
            MaterialisationLimit(LimitDimension.RETRIES, 0, "COUNT"),
            MaterialisationLimit(LimitDimension.ELAPSED_TIME, 5, "SECONDS"),
            MaterialisationLimit(LimitDimension.OBJECTS, 1, "COUNT"),
        )
        self.repository = _Repository(self._source_row())

    def tearDown(self) -> None:
        """Remove all isolated fixture data."""
        self.temporary.cleanup()

    def _source_row(self, **overrides: object) -> dict[str, object]:
        row: dict[str, object] = {
            "document_version_id": 20,
            "extraction_id": 30,
            "artefact_id": 40,
            "artefact_media_type": "application/x-orac-fixture",
            "artefact_content_sha256": self.write.identity.sha256,
            "artefact_storage_key": self.write.storage_key,
            "artefact_byte_size": self.write.identity.byte_size,
            "output_set_complete_yn": "Y",
        }
        row.update(overrides)
        return row

    def _request(
        self,
        *,
        route_disposition: P205Disposition = P205Disposition.SELECTED,
        policy_disposition: P204Disposition = P204Disposition.ACCEPT,
        safety_overrides: dict[str, object] | None = None,
        limits: tuple[MaterialisationLimit, ...] | None = None,
        expires_at: datetime | None = None,
        selection: LogicalBinarySelection | None = None,
    ) -> BinaryMaterialisationRequest:
        source_fingerprint = source_identity_fingerprint(
            document_version_id=20,
            extraction_id=30,
            artefact_id=40,
            byte_size=self.write.identity.byte_size,
            sha256=self.write.identity.sha256,
            media_type="application/x-orac-fixture",
        )
        safety_values: dict[str, object] = {
            "evidence_id": str(uuid.uuid4()),
            "evidence_version": "1.0",
            "source_fingerprint": source_fingerprint,
            "signature_valid": True,
            "structure_valid": True,
        }
        safety_values.update(safety_overrides or {})
        safety = MediaSafetyEvidence(**safety_values)
        selected = selection or LogicalBinarySelection(
            "OBJECT_SELECTION",
            (SelectionCoordinate(SelectionAxis.OBJECT, 0, 1),),
        )
        effective_limits = limits or self.dimensions
        expiry = expires_at or (self.now + timedelta(minutes=2))
        policy = P204PolicyApproval(
            result_id=str(uuid.uuid4()),
            policy_version="p2-04-v1",
            disposition=policy_disposition,
            reason_code="MEDIA_POLICY_ACCEPTED",
            source_authorisation_fingerprint=hashlib.sha256(
                b"source-authorisation"
            ).hexdigest(),
            verified_representation="fixture_binary",
            declared_mime_type="application/x-orac-fixture",
            detected_mime_type="application/x-orac-fixture",
            mime_decision=MimeDecision.EXACT,
            selection=selected,
            limits=effective_limits,
            transformation_chain=("FIXTURE_COPY",),
            required_output_representation="fixture_selection",
            safety_evidence=safety,
            evaluated_at=self.now - timedelta(seconds=1),
            expires_at=expiry,
        )
        route = P205RouteApproval(
            result_id=str(uuid.uuid4()),
            route_policy_version="p2-05-v1",
            disposition=route_disposition,
            reason_code="ROUTE_SELECTED",
            route_kind=P205RouteKind.DETERMINISTIC_PROCESSOR,
            route_identity="FIXTURE_DETERMINISTIC_ROUTE",
            processor=self.identity,
            policy_fingerprint=policy.fingerprint,
            selection_fingerprint=selected.fingerprint,
            limits_fingerprint=self._limits_fingerprint(effective_limits),
            evidence_fingerprint=safety.fingerprint,
            fallback_chain_id=str(uuid.uuid4()),
            fallback_step=0,
            locality_decision_id=str(uuid.uuid4()),
            classification_decision_id=str(uuid.uuid4()),
            consent_decision_id=str(uuid.uuid4()),
            minimisation_decision_id=str(uuid.uuid4()),
            evaluated_at=self.now - timedelta(seconds=1),
            expires_at=expiry,
        )
        return BinaryMaterialisationRequest(
            request_id=str(uuid.uuid4()),
            correlation_id=str(uuid.uuid4()),
            audit_id=str(uuid.uuid4()),
            cancellation_id=str(uuid.uuid4()),
            principal_username="fixture-principal",
            scope=KnowledgeScope("PROJECT", "ORAC_CORE"),
            document_version_id=20,
            extraction_id=30,
            artefact_id=40,
            expected_byte_size=self.write.identity.byte_size,
            expected_sha256=self.write.identity.sha256,
            source_fingerprint=source_fingerprint,
            policy=policy,
            route=route,
            expires_at=expiry,
            cleanup_deadline=expiry + timedelta(seconds=30),
        )

    @staticmethod
    def _limits_fingerprint(limits: tuple[MaterialisationLimit, ...]) -> str:
        from orac_core.knowledge.binary_materialisation import limits_fingerprint

        return limits_fingerprint(limits)

    def _service(
        self,
        processor: _FixtureProcessor | None = None,
        *,
        route_revalidator: _RouteRevalidator | None = None,
        runtime_root: Path | None = None,
        required_dimensions: frozenset[LimitDimension] | None = None,
        clock=None,
    ) -> SecureBinaryMaterialisationService:
        fixture_processor = processor or _FixtureProcessor(
            self.identity,
            measurements=(
                MaterialisationLimit(
                    LimitDimension.BYTES,
                    len(self.payload),
                    "BYTES",
                ),
                MaterialisationLimit(LimitDimension.RETRIES, 0, "COUNT"),
                MaterialisationLimit(LimitDimension.OBJECTS, 1, "COUNT"),
            ),
        )
        profile = ApprovedProcessorProfile(
            identity=self.identity,
            media_family_code="GENERIC_BINARY",
            input_representation="fixture_binary",
            output_representation="fixture_selection",
            accepted_mime_types=frozenset({"application/x-orac-fixture"}),
            required_dimensions=(
                required_dimensions
                if required_dimensions is not None
                else frozenset({LimitDimension.OBJECTS})
            ),
            allowed_selection_codes=frozenset({"OBJECT_SELECTION"}),
            processor=fixture_processor,
        )
        configuration = BinaryMaterialisationConfiguration(
            enabled=True,
            runtime_root=runtime_root or (self.root / "attachments"),
            max_source_bytes=1024,
            max_output_bytes=1024,
            max_elapsed_seconds=5,
            max_ttl_seconds=300,
            max_cleanup_grace_seconds=60,
            max_recovery_entries=32,
            max_recovery_elapsed_seconds=2,
            stale_allocation_seconds=1,
        )
        return SecureBinaryMaterialisationService(
            managed_store=self.store,
            configuration=configuration,
            source_resolver=CoreBinarySourceResolver(self.repository),
            route_revalidator=route_revalidator or _RouteRevalidator(),
            processor_profiles=(profile,),
            clock=clock,
        )

    def test_ready_handle_is_private_opaque_bound_and_single_use(self) -> None:
        request = self._request()
        service = self._service()

        result = service.materialise(request)

        self.assertEqual(result.disposition, BinaryMaterialisationDisposition.READY)
        self.assertIsNotNone(result.attachment_id)
        assert result.attachment_id is not None
        self.assertRegex(result.attachment_id, r"^[A-Za-z0-9_-]{43}$")
        rendered = repr(result)
        self.assertNotIn(self.write.storage_key, rendered)
        self.assertNotIn(str(self.root), rendered)
        attachment_root = self.root / "attachments"
        attachment_dir = attachment_root / f"att-{result.attachment_id}"
        self.assertEqual(attachment_root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(attachment_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual((attachment_dir / "payload").stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            (attachment_dir / "metadata.json").stat().st_mode & 0o777, 0o600
        )

        with service.open_attachment_once(
            result.attachment_id,
            request=request,
        ) as stream:
            self.assertEqual(stream.read(), b"safe-selection")

        self.assertFalse(attachment_dir.exists())
        with self.assertRaisesRegex(Exception, "binding|available|consumed"):
            with service.open_attachment_once(
                result.attachment_id,
                request=request,
            ):
                pass
        retry = service.materialise(request)
        self.assertEqual(retry.reason_code, "MAT_ATTACHMENT_ALREADY_CONSUMED")

    def test_non_selected_stale_and_changed_source_cannot_materialise(self) -> None:
        processor = _FixtureProcessor(
            self.identity,
            measurements=self.dimensions,
        )
        for route_disposition, expected in (
            (P205Disposition.DEFER, BinaryMaterialisationDisposition.DEFER),
            (P205Disposition.REJECT, BinaryMaterialisationDisposition.REJECT),
        ):
            with self.subTest(route_disposition=route_disposition):
                result = self._service(processor).materialise(
                    self._request(route_disposition=route_disposition)
                )
                self.assertEqual(result.disposition, expected)
                self.assertIsNone(result.attachment_id)
        stale = self._service(processor).materialise(
            self._request(expires_at=self.now - timedelta(milliseconds=1))
        )
        self.assertEqual(stale.reason_code, "MAT_APPROVAL_STALE")
        self.repository.row["artefact_content_sha256"] = "0" * 64
        changed = self._service(processor).materialise(self._request())
        self.assertEqual(changed.reason_code, "MAT_SOURCE_IDENTITY_CHANGED")
        self.assertEqual(processor.materialise_calls, 0)

    def test_contract_has_no_caller_locator_or_payload_fields(self) -> None:
        forbidden = {"path", "storage_key", "url", "filename", "credential", "payload"}
        names = {item.name for item in fields(BinaryMaterialisationRequest)}
        self.assertTrue(forbidden.isdisjoint(names))
        with self.assertRaisesRegex(ValueError, "finite and non-empty"):
            SelectionCoordinate(SelectionAxis.BYTE, 1, 1)

    def test_managed_source_symlink_permission_digest_and_size_fail_closed(
        self,
    ) -> None:
        request = self._request()
        digest = self.write.identity.sha256
        object_path = (
            self.store.managed_root / "sha256" / digest[:2] / digest[2:4] / digest
        )
        for mutation, expected in (
            ("digest", "MAT_SOURCE_CHANGED"),
            ("size", "MAT_SOURCE_CHANGED"),
            ("permission", "MAT_SOURCE_UNSAFE"),
            ("symlink", "MAT_SOURCE_UNSAFE"),
        ):
            with self.subTest(mutation=mutation):
                original = self.payload
                if object_path.is_symlink():
                    object_path.unlink()
                    object_path.write_bytes(original)
                else:
                    object_path.write_bytes(original)
                object_path.chmod(0o600)
                if mutation == "digest":
                    object_path.write_bytes(b"x" * len(original))
                elif mutation == "size":
                    object_path.write_bytes(original + b"x")
                elif mutation == "permission":
                    object_path.chmod(0o644)
                else:
                    outside = self.root / "outside"
                    outside.write_bytes(original)
                    object_path.unlink()
                    object_path.symlink_to(outside)
                result = self._service(
                    runtime_root=self.root / f"att-{mutation}"
                ).materialise(
                    replace(request, request_id=str(uuid.uuid4()), fingerprint="")
                )
                self.assertEqual(result.reason_code, expected)
                self.assertIsNone(result.attachment_id)

    def test_mime_representation_and_safety_are_checked_before_allocation(self) -> None:
        safety_cases = {
            "corrupt": "MAT_CORRUPT_CONTENT",
            "encrypted": "MAT_ENCRYPTED_CONTENT",
            "active_content": "MAT_ACTIVE_CONTENT",
            "external_references": "MAT_EXTERNAL_REFERENCE",
            "nested_content": "MAT_NESTED_CONTENT_UNSUPPORTED",
            "expansion_risk": "MAT_EXPANSION_RISK",
        }
        for flag, reason in safety_cases.items():
            with self.subTest(flag=flag):
                result = self._service(
                    runtime_root=self.root / f"safe-{flag}"
                ).materialise(self._request(safety_overrides={flag: True}))
                self.assertEqual(result.reason_code, reason)
                self.assertIsNone(result.attachment_id)
        mismatch = _FixtureProcessor(
            self.identity,
            measurements=self.dimensions,
            inspection_overrides={"detected_mime_type": "application/octet-stream"},
        )
        result = self._service(mismatch, runtime_root=self.root / "mime").materialise(
            self._request()
        )
        self.assertEqual(result.reason_code, "MAT_REPRESENTATION_MIME_MISMATCH")
        self.assertEqual(mismatch.materialise_calls, 0)

    def test_required_family_dimensions_defer_and_excess_rejects(self) -> None:
        missing_limits = tuple(
            item for item in self.dimensions if item.dimension != LimitDimension.OBJECTS
        )
        deferred = self._service(runtime_root=self.root / "missing").materialise(
            self._request(limits=missing_limits)
        )
        self.assertEqual(deferred.reason_code, "MAT_REQUIRED_BOUND_UNKNOWN")
        processor = _FixtureProcessor(
            self.identity,
            measurements=(
                MaterialisationLimit(LimitDimension.BYTES, len(self.payload), "BYTES"),
                MaterialisationLimit(LimitDimension.RETRIES, 0, "COUNT"),
                MaterialisationLimit(LimitDimension.OBJECTS, 2, "COUNT"),
            ),
        )
        rejected = self._service(
            processor, runtime_root=self.root / "exceeded"
        ).materialise(self._request())
        self.assertEqual(rejected.reason_code, "MAT_EXPANSION_LIMIT_EXCEEDED")

    def test_every_media_family_dimension_is_qualified_and_enforced(self) -> None:
        family_dimensions = (
            LimitDimension.MEMBERS,
            LimitDimension.EXPANDED_BYTES,
            LimitDimension.OBJECTS,
            LimitDimension.PAGES,
            LimitDimension.PIXELS,
            LimitDimension.CELLS,
            LimitDimension.DURATION,
            LimitDimension.CHANNELS,
            LimitDimension.FRAMES,
        )
        base_limits = tuple(
            item for item in self.dimensions if item.dimension != LimitDimension.OBJECTS
        )
        base_measurements = (
            MaterialisationLimit(LimitDimension.BYTES, len(self.payload), "BYTES"),
            MaterialisationLimit(LimitDimension.RETRIES, 0, "COUNT"),
        )
        for dimension in family_dimensions:
            with self.subTest(dimension=dimension):
                approved = MaterialisationLimit(
                    dimension,
                    1,
                    (
                        "BYTES"
                        if dimension == LimitDimension.EXPANDED_BYTES
                        else (
                            "MILLISECONDS"
                            if dimension == LimitDimension.DURATION
                            else "COUNT"
                        )
                    ),
                )
                measured = replace(approved, maximum=2)
                processor = _FixtureProcessor(
                    self.identity,
                    measurements=base_measurements + (measured,),
                )
                result = self._service(
                    processor,
                    runtime_root=self.root / f"dimension-{dimension.value.lower()}",
                    required_dimensions=frozenset({dimension}),
                ).materialise(self._request(limits=base_limits + (approved,)))
                self.assertEqual(
                    result.reason_code,
                    (
                        "MAT_EXPANSION_LIMIT_EXCEEDED"
                        if dimension
                        in {
                            LimitDimension.MEMBERS,
                            LimitDimension.EXPANDED_BYTES,
                            LimitDimension.OBJECTS,
                            LimitDimension.PAGES,
                            LimitDimension.PIXELS,
                            LimitDimension.CELLS,
                            LimitDimension.FRAMES,
                        }
                        else "MAT_BOUND_EXCEEDED"
                    ),
                )
                self.assertIsNone(result.attachment_id)

    def test_output_limit_cancellation_and_route_revalidation_cleanup(self) -> None:
        output_limit = tuple(
            (
                replace(item, maximum=4)
                if item.dimension == LimitDimension.OUTPUT_BYTES
                else item
            )
            for item in self.dimensions
        )
        exceeded = self._service(runtime_root=self.root / "output").materialise(
            self._request(limits=output_limit)
        )
        self.assertEqual(exceeded.reason_code, "MAT_OUTPUT_LIMIT_EXCEEDED")
        self.assertEqual(list((self.root / "output").iterdir()), [])

        cancelled = self._service(runtime_root=self.root / "cancel").materialise(
            self._request(),
            cancelled=lambda: True,
        )
        self.assertEqual(cancelled.reason_code, "MAT_CANCELLED")
        route_revalidator = _RouteRevalidator(approved=False)
        deferred = self._service(
            route_revalidator=route_revalidator,
            runtime_root=self.root / "route",
        ).materialise(self._request())
        self.assertEqual(deferred.reason_code, "MAT_ROUTE_REVALIDATOR_UNAVAILABLE")
        self.assertEqual(route_revalidator.calls, 1)

    def test_concurrent_retries_are_idempotent_and_cannot_cross_bind(self) -> None:
        request = self._request()
        processor = _FixtureProcessor(
            self.identity,
            measurements=(
                MaterialisationLimit(LimitDimension.BYTES, len(self.payload), "BYTES"),
                MaterialisationLimit(LimitDimension.RETRIES, 0, "COUNT"),
                MaterialisationLimit(LimitDimension.OBJECTS, 1, "COUNT"),
            ),
        )
        service = self._service(processor)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: service.materialise(request), range(8)))
        self.assertEqual(
            {result.attachment_id for result in results}, {results[0].attachment_id}
        )
        self.assertEqual(processor.materialise_calls, 1)
        different_principal = replace(
            request,
            principal_username="other-principal",
            fingerprint="",
        )
        conflict = service.materialise(different_principal)
        self.assertEqual(conflict.reason_code, "MAT_ATTACHMENT_BINDING_CONFLICT")

    def test_handle_cannot_cross_principal_request_or_route_binding(self) -> None:
        request = self._request(route_disposition=P205Disposition.FALLBACK)
        service = self._service()
        result = service.materialise(request)
        self.assertEqual(result.disposition, BinaryMaterialisationDisposition.READY)
        assert result.attachment_id is not None
        other_principal = replace(
            request,
            principal_username="other-principal",
            request_id=str(uuid.uuid4()),
            fingerprint="",
        )
        with self.assertRaisesRegex(Exception, "binding"):
            with service.open_attachment_once(
                result.attachment_id,
                request=other_principal,
            ):
                pass
        with service.open_attachment_once(
            result.attachment_id,
            request=request,
        ) as stream:
            self.assertEqual(stream.read(), b"safe-selection")

    def test_expired_handle_is_terminal_and_cleaned(self) -> None:
        request = self._request()
        current = [self.now]
        service = self._service(clock=lambda: current[0])
        result = service.materialise(request)
        assert result.attachment_id is not None
        attachment_dir = self.root / "attachments" / f"att-{result.attachment_id}"
        current[0] = request.expires_at + timedelta(seconds=1)

        with self.assertRaises(Exception) as raised:
            with service.open_attachment_once(
                result.attachment_id,
                request=request,
            ):
                pass

        self.assertEqual(
            getattr(raised.exception, "reason_code", None),
            "MAT_ATTACHMENT_EXPIRED",
        )
        self.assertFalse(attachment_dir.exists())

    def test_attachment_permission_tamper_fails_closed_without_unsafe_deletion(
        self,
    ) -> None:
        request = self._request()
        service = self._service()
        result = service.materialise(request)
        assert result.attachment_id is not None
        attachment_dir = self.root / "attachments" / f"att-{result.attachment_id}"
        payload_path = attachment_dir / "payload"
        payload_path.chmod(0o644)

        with self.assertRaises(Exception) as raised:
            with service.open_attachment_once(
                result.attachment_id,
                request=request,
            ):
                pass

        self.assertEqual(
            getattr(raised.exception, "reason_code", None),
            "MAT_ATTACHMENT_PERMISSION_INVALID",
        )
        self.assertTrue(attachment_dir.exists())
        status = service.attachment_status(result.attachment_id)
        self.assertIsNotNone(status)
        assert status is not None
        self.assertEqual(status.cleanup_state.value, "CLEANUP_FAILED")
        recovery = service.reconcile_startup()
        self.assertGreaterEqual(recovery.ambiguous_entries, 1)
        self.assertTrue(attachment_dir.exists())

    def test_elapsed_time_expiry_cleans_partial_attachment(self) -> None:
        class _TimedOutProcessor(_FixtureProcessor):
            def materialise(self, source, sink, *, selection, limits, check_terminal):
                del source, selection, limits
                sink.write(b"partial")
                time.sleep(1.01)
                check_terminal()
                raise AssertionError("deadline check should be terminal")

        limits = tuple(
            (
                replace(item, maximum=1)
                if item.dimension == LimitDimension.ELAPSED_TIME
                else item
            )
            for item in self.dimensions
        )
        processor = _TimedOutProcessor(
            self.identity,
            measurements=(
                MaterialisationLimit(LimitDimension.BYTES, len(self.payload), "BYTES"),
                MaterialisationLimit(LimitDimension.RETRIES, 0, "COUNT"),
                MaterialisationLimit(LimitDimension.OBJECTS, 1, "COUNT"),
            ),
        )
        result = self._service(
            processor, runtime_root=self.root / "timeout"
        ).materialise(self._request(limits=limits))
        self.assertEqual(result.reason_code, "MAT_ELAPSED_TIME_EXPIRED")
        self.assertEqual(list((self.root / "timeout").iterdir()), [])

    def test_p2_06_has_no_provider_model_or_plugin_attachment_dependency(self) -> None:
        module_text = (
            PROJECT_ROOT
            / "src"
            / "orac_core"
            / "knowledge"
            / "binary_materialisation.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "provider_registry",
            "llm_connector",
            "PluginManager",
            "list_models",
            "pull_model",
            "load_model",
        ):
            self.assertNotIn(forbidden, module_text)

    def test_restart_recovers_only_valid_live_entries_and_reports_ambiguity(
        self,
    ) -> None:
        request = self._request()
        runtime_root = self.root / "recovery"
        first = self._service(runtime_root=runtime_root)
        result = first.materialise(request)
        self.assertIsNotNone(result.attachment_id)
        ambiguous = runtime_root / "caller-path"
        ambiguous.write_text("do not delete", encoding="utf-8")

        second = self._service(runtime_root=runtime_root)
        report = second.reconcile_startup()

        self.assertEqual(report.recovered_ready, 1)
        self.assertEqual(report.ambiguous_entries, 1)
        self.assertTrue(ambiguous.exists())

    def test_elapsed_deadline_and_authoritative_derivative_provenance(self) -> None:
        class _SlowProcessor(_FixtureProcessor):
            def materialise(self, source, sink, *, selection, limits, check_terminal):
                time.sleep(0.01)
                check_terminal()
                return super().materialise(
                    source,
                    sink,
                    selection=selection,
                    limits=limits,
                    check_terminal=check_terminal,
                )

        elapsed_limits = tuple(
            (
                replace(item, maximum=1)
                if item.dimension == LimitDimension.ELAPSED_TIME
                else item
            )
            for item in self.dimensions
        )
        processor = _SlowProcessor(
            self.identity,
            measurements=(
                MaterialisationLimit(LimitDimension.BYTES, len(self.payload), "BYTES"),
                MaterialisationLimit(LimitDimension.RETRIES, 0, "COUNT"),
                MaterialisationLimit(LimitDimension.OBJECTS, 1, "COUNT"),
            ),
        )
        result = self._service(
            processor, runtime_root=self.root / "authoritative"
        ).materialise(self._request(limits=elapsed_limits))
        self.assertEqual(result.disposition, BinaryMaterialisationDisposition.READY)
        self.assertIsNotNone(result.derivative)
        assert result.derivative is not None
        self.assertTrue(result.derivative.authoritative)
        self.assertEqual(result.derivative.processor, self.identity)


if __name__ == "__main__":
    unittest.main()
