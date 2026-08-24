"""Build deterministic model-visible envelopes from approved knowledge evidence."""

# Author: Clive Bostock
# Date: 14-Aug-2026
# Description: Serialises verified P1-07 text evidence behind a canonical trust boundary.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass
import csv
import hashlib
import io
import json
import re
from typing import Any, Mapping

from .materialisation import KnowledgeRetrievedPart
from .materialisation_policy import MaterialisationDecisionCode
from .materialisation_policy import ProgressiveMaterialisationResult
from .token_estimation import ConservativeUtf8TokenEstimator


EVIDENCE_ENVELOPE_VERSION = 1
EVIDENCE_BEGIN_MARKER = "ORAC_UNTRUSTED_EVIDENCE_BEGIN version=1"
EVIDENCE_END_MARKER = "ORAC_UNTRUSTED_EVIDENCE_END version=1"

_MEDIA_FORMATS = {
    "application/json": "json",
    "text/csv": "csv",
    "text/markdown": "markdown",
    "text/plain": "plain_text",
}
_ARTEFACT_ROLES = {"PRIMARY", "MEMBER", "MANIFEST", "TABLE"}
_A1_RANGE = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*:[A-Z]{1,3}[1-9][0-9]*$")


class EvidenceEnvelopeError(ValueError):
    """Raised when approved evidence cannot be framed safely."""

    def __init__(self, reason_code: str) -> None:
        """Initialise the failure with a safe P1-08 reason code."""
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    """Immutable canonical evidence rendered for a flat-text model adapter."""

    version: int
    text: str
    byte_size: int
    safe_token_count: int
    part_count: int
    content_digest: str
    complete: bool
    selected: bool
    downgraded: bool
    non_truncated: bool
    source_byte_size: int = 0
    effective_level: str = ""
    member_count: int = 0
    chunk_count: int = 0
    row_count: int = 0


class KnowledgeEvidenceEnvelopeBuilder:
    """Validate P1-07 output and emit the canonical JSON evidence envelope."""

    def __init__(
        self,
        *,
        estimator: ConservativeUtf8TokenEstimator | None = None,
    ) -> None:
        """Initialise the builder with the existing conservative estimator."""
        self._estimator = estimator or ConservativeUtf8TokenEstimator()

    def build(self, result: ProgressiveMaterialisationResult) -> EvidenceEnvelope:
        """Build one deterministic non-truncated envelope.

        Args:
            result (ProgressiveMaterialisationResult): Verified P1-07 output.

        Returns:
            EvidenceEnvelope: Canonical single-line JSON inside fixed markers.

        Raises:
            EvidenceEnvelopeError: If verification, media, provenance, or
                canonical framing is invalid.
        """
        decision = result.decision
        if decision.decision_code not in {
            MaterialisationDecisionCode.APPROVED,
            MaterialisationDecisionCode.DOWNGRADED,
        }:
            raise EvidenceEnvelopeError("MAT_SUB_ENVELOPE_INVALID")
        if decision.effective_level is None or not result.parts:
            raise EvidenceEnvelopeError("MAT_SUB_ENVELOPE_INVALID")
        if decision.truncated:
            raise EvidenceEnvelopeError("MAT_SUB_VERIFICATION_FAILED")
        if not result.verified or result.accounting is None:
            raise EvidenceEnvelopeError("MAT_SUB_VERIFICATION_FAILED")
        if not result.accounting.verified:
            raise EvidenceEnvelopeError("MAT_SUB_VERIFICATION_FAILED")

        document_labels: dict[int, str] = {}
        visible_parts: list[dict[str, Any]] = []
        row_count = 0
        for ordinal, part in enumerate(result.parts, start=1):
            visible_part = self._visible_part(
                    part,
                    ordinal=ordinal,
                    document_labels=document_labels,
                )
            visible_parts.append(visible_part)
            if visible_part["content_format"] == "csv":
                try:
                    row_count += sum(
                        1 for _ in csv.reader(io.StringIO(visible_part["content"]))
                    )
                except csv.Error as exc:
                    raise EvidenceEnvelopeError("MAT_SUB_ENVELOPE_INVALID") from exc

        body = {
            "decision": {
                "complete": decision.complete,
                "decision_code": decision.decision_code.value,
                "downgraded": decision.downgraded,
                "effective_level": decision.effective_level.value,
                "non_truncated": not decision.truncated,
                "requested_level": decision.requested_level.value,
                "selected": decision.selected,
            },
            "parts": visible_parts,
            "schema": "orac.untrusted_evidence",
            "version": EVIDENCE_ENVELOPE_VERSION,
        }
        try:
            canonical = json.dumps(
                body,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
                separators=(",", ":"),
            )
            if "\n" in canonical or "\r" in canonical:
                raise ValueError("canonical JSON contains a physical newline")
            rendered = (
                f"{EVIDENCE_BEGIN_MARKER}\n{canonical}\n{EVIDENCE_END_MARKER}"
            )
            payload = rendered.encode("utf-8", errors="strict")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise EvidenceEnvelopeError("MAT_SUB_ENVELOPE_INVALID") from exc
        rendered_lines = rendered.splitlines()
        if rendered_lines != [EVIDENCE_BEGIN_MARKER, canonical, EVIDENCE_END_MARKER]:
            raise EvidenceEnvelopeError("MAT_SUB_INJECTION_BOUNDARY_FAILED")

        estimate = self._estimator.estimate_envelope(rendered)
        source_byte_size = sum(len(part.content) for part in result.parts)
        effective_level = decision.effective_level.value
        chunk_count = (
            len(visible_parts)
            if effective_level in {"RELEVANT_CHUNKS", "SURROUNDING_CONTEXT"}
            else 0
        )
        member_count = len(visible_parts) - chunk_count
        return EvidenceEnvelope(
            version=EVIDENCE_ENVELOPE_VERSION,
            text=rendered,
            byte_size=len(payload),
            safe_token_count=estimate.safe_token_count,
            part_count=len(visible_parts),
            content_digest=hashlib.sha256(payload).hexdigest(),
            complete=decision.complete,
            selected=decision.selected,
            downgraded=decision.downgraded,
            non_truncated=not decision.truncated,
            source_byte_size=source_byte_size,
            effective_level=effective_level,
            member_count=member_count,
            chunk_count=chunk_count,
            row_count=row_count,
        )

    def _visible_part(
        self,
        part: KnowledgeRetrievedPart,
        *,
        ordinal: int,
        document_labels: dict[int, str],
    ) -> dict[str, Any]:
        """Return one content part with allowlisted model-visible provenance."""
        content = self._verified_content(part)
        media_type, content_format = _media_contract(part.provenance)
        provenance = _visible_provenance(
            part.provenance,
            ordinal=ordinal,
            document_labels=document_labels,
        )
        return {
            "content": content,
            "content_format": content_format,
            "media_type": media_type,
            "ordinal": ordinal,
            "provenance": provenance,
        }

    @staticmethod
    def _verified_content(part: KnowledgeRetrievedPart) -> str:
        """Strictly decode and re-verify one P1-06/P1-07 payload."""
        if not isinstance(part.content, bytes):
            raise EvidenceEnvelopeError("MAT_SUB_VERIFICATION_FAILED")
        try:
            text = part.content.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise EvidenceEnvelopeError("MAT_SUB_VERIFICATION_FAILED") from exc
        verification = part.verification
        status = str(verification.get("status") or "")
        emitted_size = _optional_int(verification.get("emitted_byte_size"))
        emitted_digest = str(verification.get("emitted_sha256") or "")
        observed_digest = hashlib.sha256(part.content).hexdigest()
        if not status.startswith("VERIFIED"):
            raise EvidenceEnvelopeError("MAT_SUB_VERIFICATION_FAILED")
        if emitted_size is not None and emitted_size != len(part.content):
            raise EvidenceEnvelopeError("MAT_SUB_VERIFICATION_FAILED")
        if emitted_digest and emitted_digest != observed_digest:
            raise EvidenceEnvelopeError("MAT_SUB_VERIFICATION_FAILED")
        return text


def _media_contract(provenance: Mapping[str, Any]) -> tuple[str, str]:
    """Return the canonical approved media type and visible content format."""
    raw = str(provenance.get("media_type") or "").strip().lower()
    base = raw.split(";", 1)[0].strip()
    content_format = _MEDIA_FORMATS.get(base)
    if content_format is None:
        raise EvidenceEnvelopeError("MAT_SUB_MEDIA_UNSUPPORTED")
    if ";" in raw and "charset=utf-8" not in raw.replace(" ", ""):
        raise EvidenceEnvelopeError("MAT_SUB_MEDIA_UNSUPPORTED")
    media_type = (
        "application/json; charset=utf-8"
        if base == "application/json"
        else f"{base}; charset=utf-8"
    )
    return media_type, content_format


def _visible_provenance(
    source: Mapping[str, Any],
    *,
    ordinal: int,
    document_labels: dict[int, str],
) -> dict[str, Any]:
    """Build model-visible provenance from controlled scalar identities only."""
    document_id = _required_positive_int(source, "document_id")
    document_version_id = _required_positive_int(source, "document_version_id")
    if document_id not in document_labels:
        document_labels[document_id] = f"Document {len(document_labels) + 1}"

    result: dict[str, Any] = {
        "document_id": document_id,
        "document_label": document_labels[document_id],
        "document_version_id": document_version_id,
    }
    extraction_id = _first_positive_int(source, "extraction_id")
    if extraction_id is None:
        raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
    result["extraction_id"] = extraction_id

    chunk_id = _first_positive_int(source, "chunk_id")
    if chunk_id is not None:
        result.update(_chunk_provenance(source, chunk_id=chunk_id))
        return result

    artefact_id = _first_positive_int(source, "artefact_id", "source_artefact_id")
    legacy = bool(source.get("legacy_artefact_provenance"))
    if artefact_id is None and not legacy:
        raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
    result["artefact_id"] = artefact_id
    if legacy:
        result["legacy_source_kind"] = "EXTRACTION_CLOB"
        return result

    role = str(
        source.get("artefact_role") or source.get("source_artefact_role") or ""
    ).strip().upper()
    if role not in _ARTEFACT_ROLES:
        raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
    result["artefact_role"] = role
    member_ordinal = _first_positive_int(source, "member_ordinal")
    if member_ordinal is not None:
        result["member_ordinal"] = member_ordinal

    _copy_label(source, result, "worksheet_name", "worksheet_label")
    _copy_label(source, result, "table_name", "table_label")
    _copy_label(source, result, "section_label", "section_label")
    _copy_a1(source, result, "source_cell_range", "source_cell_range")
    selection = source.get("selection")
    if isinstance(selection, Mapping):
        _copy_a1(selection, result, "cell_range", "selected_cell_range")
    header_rows = source.get("header_rows") or source.get("source_header_rows")
    normalised_rows = _positive_int_tuple(header_rows)
    if normalised_rows:
        result["header_rows"] = list(normalised_rows)
    hidden = source.get("hidden_sheet")
    if hidden is not None:
        result["hidden_sheet"] = _boolean_value(hidden)
    return result


def _chunk_provenance(source: Mapping[str, Any], *, chunk_id: int) -> dict[str, Any]:
    """Return required lineage for a selected registered chunk."""
    chunk_no = _required_positive_int(source, "chunk_no")
    chunk_set_id = _first_positive_int(source, "chunk_set_id")
    artefact_id = _first_positive_int(source, "source_artefact_id", "artefact_id")
    if chunk_set_id is None or artefact_id is None:
        raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
    return {
        "artefact_id": artefact_id,
        "chunk_id": chunk_id,
        "chunk_no": chunk_no,
        "chunk_set_id": chunk_set_id,
    }


def _copy_label(
    source: Mapping[str, Any],
    target: dict[str, Any],
    source_key: str,
    target_key: str,
) -> None:
    """Copy a bounded presentation label without accepting control characters."""
    value = source.get(source_key)
    if value in (None, ""):
        return
    label = str(value).strip()
    if not label or len(label) > 255 or any(ord(char) < 32 for char in label):
        raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
    target[target_key] = label


def _copy_a1(
    source: Mapping[str, Any],
    target: dict[str, Any],
    source_key: str,
    target_key: str,
) -> None:
    """Copy a canonical bounded A1 range."""
    value = source.get(source_key)
    if value in (None, ""):
        return
    cell_range = str(value).strip().upper()
    if _A1_RANGE.fullmatch(cell_range) is None:
        raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
    target[target_key] = cell_range


def _required_positive_int(source: Mapping[str, Any], key: str) -> int:
    """Return a required positive integer provenance field."""
    value = _first_positive_int(source, key)
    if value is None:
        raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
    return value


def _first_positive_int(source: Mapping[str, Any], *keys: str) -> int | None:
    """Return the first present positive integer without accepting booleans."""
    for key in keys:
        if source.get(key) is None:
            continue
        value = _optional_int(source.get(key))
        if value is None or value <= 0:
            raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
        return value
    return None


def _optional_int(value: Any) -> int | None:
    """Return an integer when the input is an integer-like scalar."""
    if value is None or isinstance(value, bool):
        return None
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return None
    return converted


def _positive_int_tuple(value: Any) -> tuple[int, ...]:
    """Return a bounded tuple of positive row ordinals."""
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID") from exc
    if not isinstance(value, (list, tuple)) or len(value) > 32:
        raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
    rows: list[int] = []
    for item in value:
        converted = _optional_int(item)
        if converted is None or converted <= 0:
            raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
        rows.append(converted)
    return tuple(rows)


def _boolean_value(value: Any) -> bool:
    """Return a strict boolean from database or Python scalar forms."""
    if isinstance(value, bool):
        return value
    normalised = str(value).strip().upper()
    if normalised in {"Y", "TRUE"}:
        return True
    if normalised in {"N", "FALSE"}:
        return False
    raise EvidenceEnvelopeError("MAT_SUB_PROVENANCE_INVALID")
