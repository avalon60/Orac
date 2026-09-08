"""Content-free durable audit adapter for governed model retrieval."""

# Author: Clive Bostock
# Date: 2026-09-07
# Description: Records allowlisted Phase 2A execution metadata through ORAC_CODE.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import json
from typing import Any, Callable, Mapping
import uuid

from orac_core.knowledge.repository import default_orac_session


class GovernedRetrievalAuditRepository:
    """Call the existing append-only retrieval audit boundary."""

    _PACKAGE = "orac_code.knowledge_retrieval_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise with an optional runtime session factory."""
        self._session_factory = session_factory or default_orac_session

    def record_turn(
        self,
        *,
        principal_username: str,
        domain_code: str,
        status_code: str,
        reason_code: str,
        tool_mode: str,
        tool_timing: str,
        stream_health_state: str,
        committed_before_tool: bool,
        continuation_recovery: bool,
        final_invocation_id: str | None,
        duration_ms: int | None,
        phase2c_detail: Mapping[str, Any] | None = None,
    ) -> str:
        """Persist one content-free terminal event and return its UUID."""
        event_id = str(uuid.uuid4())
        phase2c_json = _phase2c_json(phase2c_detail)
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(
                    f"{self._PACKAGE}.record_governed_retrieval_event",
                    [
                        event_id,
                        principal_username,
                        domain_code,
                        status_code,
                        reason_code,
                        tool_mode,
                        tool_timing,
                        stream_health_state,
                        "Y" if committed_before_tool else "N",
                        "Y" if continuation_recovery else "N",
                        final_invocation_id,
                        duration_ms,
                        phase2c_json,
                    ],
                )
            session.commit()
            return event_id
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()


def _phase2c_json(detail: Mapping[str, Any] | None) -> str | None:
    """Validate the content-free Phase 2C telemetry contract before persistence."""
    if not detail:
        return None
    allowed_top = {
        "schema_version",
        "discovery",
        "retrieval_required",
        "retrieval_requirement_reasons",
        "decision_attempt_count",
        "discarded_decision_characters",
        "selected_handles",
        "successful_domain_types",
        "unavailable_domain_count",
        "selected_evidence_count",
        "omitted_evidence_count",
        "retrieval_status",
        "continuation_suppressed",
        "host_safe_response",
    }
    allowed_discovery = {
        "authorised_catalogue_size",
        "domains_scored",
        "semantic_matches",
        "semantic_advertised_count",
        "conversation_advertised_count",
        "advertised_count",
        "cache_hits",
        "cache_misses",
        "embedding_batches",
        "conversation_available",
        "fallback_mode",
        "duration_ms",
        "profile_identity",
        "advertised",
        "candidate_counts",
    }
    if set(detail) - allowed_top:
        raise ValueError("Phase 2C audit detail contains unsupported fields")
    discovery = detail.get("discovery")
    if not isinstance(discovery, Mapping) or set(discovery) - allowed_discovery:
        raise ValueError("Phase 2C discovery audit detail is invalid")
    requirement_reasons = detail.get("retrieval_requirement_reasons", [])
    if (
        not isinstance(requirement_reasons, list)
        or len(requirement_reasons) > 2
        or any(
            item
            not in {
                "EXPLICIT_LOCAL_RETRIEVAL_INTENT",
                "SEMANTIC_DOMAIN_MATCH",
            }
            for item in requirement_reasons
        )
    ):
        raise ValueError("Phase 2C retrieval requirement detail is invalid")
    if not isinstance(detail.get("retrieval_required", False), bool):
        raise ValueError("Phase 2C retrieval requirement flag is invalid")
    for flag in ("continuation_suppressed", "host_safe_response"):
        if not isinstance(detail.get(flag, False), bool):
            raise ValueError(f"Phase 2C {flag} flag is invalid")
    retrieval_status = detail.get("retrieval_status")
    if retrieval_status is not None and retrieval_status not in {
        "grounded",
        "no_evidence",
        "unavailable",
        "denied",
        "invalid",
        "failed",
    }:
        raise ValueError("Phase 2C retrieval status is invalid")
    decision_attempt_count = detail.get("decision_attempt_count", 0)
    if (
        not isinstance(decision_attempt_count, int)
        or not 0 <= decision_attempt_count <= 2
    ):
        raise ValueError("Phase 2C decision attempt count is invalid")
    discarded_characters = detail.get("discarded_decision_characters", 0)
    if not isinstance(discarded_characters, int) or discarded_characters < 0:
        raise ValueError("Phase 2C discarded character count is invalid")
    advertised = discovery.get("advertised", [])
    if not isinstance(advertised, list) or len(advertised) > 8:
        raise ValueError("Phase 2C advertised audit detail is invalid")
    allowed_advertisement = {
        "handle",
        "domain_type",
        "relevance_score",
        "domain_weight",
    }
    if any(
        not isinstance(item, Mapping) or set(item) - allowed_advertisement
        for item in advertised
    ):
        raise ValueError("Phase 2C advertisement audit fields are invalid")
    candidate_counts = discovery.get("candidate_counts", {})
    if not isinstance(candidate_counts, Mapping) or len(candidate_counts) > 8:
        raise ValueError("Phase 2C candidate count audit detail is invalid")
    encoded = json.dumps(
        dict(detail),
        ensure_ascii=True,
        separators=(",", ":"),
    )
    if len(encoded.encode("utf-8")) > 8192:
        raise ValueError("Phase 2C audit detail exceeds 8 KiB")
    return encoded
