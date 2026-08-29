"""Content-free durable audit adapter for governed model retrieval."""
# Author: Clive Bostock
# Date: 2026-08-29
# Description: Records allowlisted Phase 2A execution metadata through ORAC_CODE.

from __future__ import annotations

from typing import Any, Callable
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
    ) -> str:
        """Persist one content-free terminal event and return its UUID."""
        event_id = str(uuid.uuid4())
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
                    ],
                )
            session.commit()
            return event_id
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()
