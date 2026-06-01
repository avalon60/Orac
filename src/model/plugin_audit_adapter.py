"""Runtime adapter for durable plugin audit persistence."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Normalises plugin lifecycle metadata and writes it through the
#   approved Orac database API when runtime database access is available.

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
import json
from typing import Any

try:
    import oracledb
except Exception:  # pragma: no cover - test/runtime fallback
    class _OracledbStub:
        NUMBER = object()

    oracledb = _OracledbStub()


def _as_int(value: Any) -> int | None:
    """Return an integer value when conversion is safe."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _as_float(value: Any) -> float | None:
    """Return a float value when conversion is safe."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _as_tuple(value: Any) -> tuple[str, ...]:
    """Return a stable string tuple for JSON-friendly sequence values."""
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    if isinstance(value, set):
        return tuple(str(item) for item in sorted(value))
    return (str(value),)


def _json_payload(value: Any) -> str | None:
    """Return a safe JSON string for database binds."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


@dataclass(frozen=True)
class PluginAuditPayload:
    """Normalised plugin audit data ready for the Orac database API."""

    request_id: str | None = None
    correlation_id: str | None = None
    turn_id: str | None = None
    conversation_id: int | None = None
    message_id: int | None = None
    user_id: int | None = None
    plugin_id: str = ""
    plugin_name: str = ""
    action_type: str = ""
    capabilities: tuple[str, ...] = ()
    entitlements: tuple[str, ...] = ()
    policy_decision: str | None = None
    confirmation_id: str | None = None
    confirmation_status: str | None = None
    execution_status: str | None = None
    timeout_seconds: float | None = None
    failure_type: str | None = None
    failure_message: str | None = None
    provenance_json: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_provenance(
        cls,
        provenance: dict[str, Any] | None,
        *,
        request_context: dict[str, Any] | None = None,
        policy_decision: str | None = None,
        confirmation_status: str | None = None,
        execution_status: str | None = None,
        timeout_seconds: float | None = None,
        failure_type: str | None = None,
        failure_message: str | None = None,
    ) -> "PluginAuditPayload":
        """Build a payload from Orac-owned plugin provenance."""
        provenance = dict(provenance or {})
        request_context = dict(request_context or {})

        confirmation_data = provenance.get("confirmation")
        confirmation_data = confirmation_data if isinstance(confirmation_data, dict) else {}
        confirmation_request = provenance.get("confirmation_request")
        confirmation_request = (
            confirmation_request if isinstance(confirmation_request, dict) else {}
        )

        plugin_id = str(provenance.get("plugin_id") or request_context.get("plugin_id") or "")
        plugin_name = str(provenance.get("plugin_name") or request_context.get("plugin_name") or "")
        action_type = str(provenance.get("action_type") or request_context.get("action_type") or "")

        capabilities = _as_tuple(provenance.get("capabilities") or request_context.get("capabilities"))
        entitlements = _as_tuple(provenance.get("entitlements") or request_context.get("entitlements"))

        decision = policy_decision or str(provenance.get("policy_decision") or provenance.get("status") or "").strip() or None
        execution_state = execution_status or str(provenance.get("status") or "").strip() or None
        if execution_state is None and decision in {"denied", "requires_confirmation"}:
            execution_state = decision
        if execution_state is None and decision == "allowed":
            execution_state = "completed"

        if confirmation_status is None:
            confirmation_status = (
                str(confirmation_data.get("status") or "").strip()
                or str(confirmation_request.get("status") or "").strip()
                or None
            )
        confirmation_id = str(
            provenance.get("confirmation_id")
            or confirmation_data.get("confirmation_id")
            or confirmation_request.get("confirmation_id")
            or ""
        ).strip() or None

        request_id = str(
            request_context.get("request_id")
            or request_context.get("req_id")
            or provenance.get("request_id")
            or ""
        ).strip() or None
        correlation_id = str(
            request_context.get("correlation_id")
            or provenance.get("correlation_id")
            or request_id
            or ""
        ).strip() or None
        turn_id = str(
            request_context.get("turn_id")
            or provenance.get("turn_id")
            or ""
        ).strip() or None

        return cls(
            request_id=request_id,
            correlation_id=correlation_id,
            turn_id=turn_id,
            conversation_id=_as_int(
                request_context.get("conversation_id") or provenance.get("conversation_id")
            ),
            message_id=_as_int(request_context.get("message_id") or provenance.get("message_id")),
            user_id=_as_int(request_context.get("user_id") or provenance.get("user_id")),
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            action_type=action_type,
            capabilities=capabilities,
            entitlements=entitlements,
            policy_decision=decision,
            confirmation_id=confirmation_id,
            confirmation_status=confirmation_status,
            execution_status=execution_state,
            timeout_seconds=_as_float(timeout_seconds or provenance.get("timeout_seconds")),
            failure_type=str(failure_type or provenance.get("failure_type") or "").strip() or None,
            failure_message=str(
                failure_message or provenance.get("failure_message") or ""
            ).strip()
            or None,
            provenance_json=provenance,
        )


@dataclass
class PluginAuditSession:
    """Tracks one plugin invocation as it moves through the audit API."""

    adapter: "PluginAuditAdapter"
    payload: PluginAuditPayload
    plugin_invocation_id: int | None = None
    row_version: int | None = None

    def record_policy_decision(
        self,
        *,
        policy_decision: str,
        policy_reason: str | None = None,
        event_message: str | None = None,
        provenance_json: dict[str, Any] | None = None,
    ) -> int | None:
        """Persist a policy decision event for this invocation."""
        if self.plugin_invocation_id is None:
            return None
        self.row_version = self.adapter.record_policy_decision(
            plugin_invocation_id=self.plugin_invocation_id,
            policy_decision=policy_decision,
            policy_reason=policy_reason,
            event_message=event_message,
            provenance_json=provenance_json or self.payload.provenance_json,
        )
        return self.row_version

    def record_confirmation_event(
        self,
        *,
        event_type: str,
        confirmation_id: str | None,
        confirmation_status: str | None,
        event_message: str | None = None,
        event_payload_json: dict[str, Any] | None = None,
    ) -> int | None:
        """Persist a confirmation lifecycle event for this invocation."""
        if self.plugin_invocation_id is None:
            return None
        self.row_version = self.adapter.record_confirmation_event(
            plugin_invocation_id=self.plugin_invocation_id,
            event_type=event_type,
            confirmation_id=confirmation_id,
            confirmation_status=confirmation_status,
            event_message=event_message,
            event_payload_json=event_payload_json or self.payload.provenance_json,
        )
        return self.row_version

    def record_execution_event(
        self,
        *,
        event_type: str,
        execution_status: str,
        timeout_seconds: float | None = None,
        failure_type: str | None = None,
        failure_message: str | None = None,
        provenance_json: dict[str, Any] | None = None,
    ) -> int | None:
        """Persist an execution lifecycle event for this invocation."""
        if self.plugin_invocation_id is None:
            return None
        self.row_version = self.adapter.record_execution_event(
            plugin_invocation_id=self.plugin_invocation_id,
            event_type=event_type,
            execution_status=execution_status,
            timeout_seconds=timeout_seconds,
            failure_type=failure_type,
            failure_message=failure_message,
            provenance_json=provenance_json or self.payload.provenance_json,
        )
        return self.row_version

    def link_message(self, message_id: int | None) -> int | None:
        """Attach a persisted assistant message to this invocation."""
        if self.plugin_invocation_id is None or message_id is None:
            return None
        self.row_version = self.adapter.link_message(
            plugin_invocation_id=self.plugin_invocation_id,
            message_id=message_id,
        )
        return self.row_version


class PluginAuditAdapter:
    """Writes plugin lifecycle rows through the approved code API when possible."""

    def __init__(self, *, db_session: Any | None, logger: Any, strict: bool = False) -> None:
        """Initialise the adapter.

        Args:
            db_session: Orac database session used to call the code package.
            logger: Project logger used for safe operational messages.
            strict: When true, audit write failures are re-raised instead of
                being downgraded to a best-effort no-op.
        """
        self._db_session = db_session
        self._logger = logger
        self._strict = bool(strict)

    def create_session(
        self,
        *,
        provenance: dict[str, Any] | None,
        request_context: dict[str, Any] | None = None,
        policy_decision: str | None = None,
        confirmation_status: str | None = None,
        execution_status: str | None = None,
        timeout_seconds: float | None = None,
        failure_type: str | None = None,
        failure_message: str | None = None,
    ) -> PluginAuditSession:
        """Normalise one plugin lifecycle snapshot into a writable session."""
        payload = PluginAuditPayload.from_provenance(
            provenance,
            request_context=request_context,
            policy_decision=policy_decision,
            confirmation_status=confirmation_status,
            execution_status=execution_status,
            timeout_seconds=timeout_seconds,
            failure_type=failure_type,
            failure_message=failure_message,
        )
        session = PluginAuditSession(adapter=self, payload=payload)
        if self._db_session is None or not hasattr(self._db_session, "cursor"):
            self._log_unavailable("begin_invocation")
            return session

        try:
            session.plugin_invocation_id, session.row_version = self._begin_invocation(payload)
        except Exception as exc:
            self._log_failure("begin_invocation", exc)
            if self._strict:
                raise
        return session

    def record_policy_decision(
        self,
        *,
        plugin_invocation_id: int,
        policy_decision: str,
        policy_reason: str | None = None,
        event_message: str | None = None,
        provenance_json: dict[str, Any] | None = None,
    ) -> int | None:
        """Persist a policy decision and return the updated row version."""
        try:
            return self._call_package(
                "record_policy_decision",
                plugin_invocation_id=plugin_invocation_id,
                policy_decision=policy_decision,
                policy_reason=policy_reason,
                event_message=event_message,
                provenance_json=provenance_json,
            )
        except Exception as exc:
            self._log_failure("record_policy_decision", exc)
            if self._strict:
                raise
            return None

    def record_confirmation_event(
        self,
        *,
        plugin_invocation_id: int,
        event_type: str,
        confirmation_id: str | None,
        confirmation_status: str | None,
        event_message: str | None = None,
        event_payload_json: dict[str, Any] | None = None,
    ) -> int | None:
        """Persist a confirmation lifecycle event."""
        try:
            return self._call_package(
                "record_confirmation_event",
                plugin_invocation_id=plugin_invocation_id,
                event_type=event_type,
                confirmation_id=confirmation_id,
                confirmation_status=confirmation_status,
                event_message=event_message,
                event_payload_json=event_payload_json,
            )
        except Exception as exc:
            self._log_failure("record_confirmation_event", exc)
            if self._strict:
                raise
            return None

    def record_execution_event(
        self,
        *,
        plugin_invocation_id: int,
        event_type: str,
        execution_status: str,
        timeout_seconds: float | None = None,
        failure_type: str | None = None,
        failure_message: str | None = None,
        provenance_json: dict[str, Any] | None = None,
    ) -> int | None:
        """Persist an execution lifecycle event."""
        try:
            return self._call_package(
                "record_execution_event",
                plugin_invocation_id=plugin_invocation_id,
                event_type=event_type,
                execution_status=execution_status,
                timeout_seconds=timeout_seconds,
                failure_type=failure_type,
                failure_message=failure_message,
                provenance_json=provenance_json,
            )
        except Exception as exc:
            self._log_failure("record_execution_event", exc)
            if self._strict:
                raise
            return None

    def link_message(
        self,
        *,
        plugin_invocation_id: int,
        message_id: int,
    ) -> int | None:
        """Link a persisted assistant message to a plugin invocation."""
        try:
            return self._call_package(
                "link_message",
                plugin_invocation_id=plugin_invocation_id,
                message_id=message_id,
            )
        except Exception as exc:
            self._log_failure("link_message", exc)
            if self._strict:
                raise
            return None

    def _begin_invocation(self, payload: PluginAuditPayload) -> tuple[int, int | None]:
        """Call the package begin-invocation procedure."""
        if self._db_session is None:
            raise RuntimeError("Plugin audit DB session is unavailable.")

        block = """
begin
  orac_code.plugin_audit_api.begin_invocation(
    p_plugin_invocation_id => :plugin_invocation_id,
    p_row_version => :row_version,
    p_plugin_id => :plugin_id,
    p_plugin_name => :plugin_name,
    p_action_type => :action_type,
    p_request_id => :request_id,
    p_correlation_id => :correlation_id,
    p_turn_id => :turn_id,
    p_conversation_id => :conversation_id,
    p_message_id => :message_id,
    p_user_id => :user_id,
    p_capabilities => :capabilities,
    p_entitlements => :entitlements,
    p_provenance_json => :provenance_json
  );
end;
"""
        with self._db_session.cursor() as cursor:
            plugin_invocation_id = cursor.var(oracledb.NUMBER)
            row_version = cursor.var(oracledb.NUMBER)
            cursor.execute(
                block,
                {
                    "plugin_invocation_id": plugin_invocation_id,
                    "row_version": row_version,
                    "plugin_id": payload.plugin_id,
                    "plugin_name": payload.plugin_name,
                    "action_type": payload.action_type,
                    "request_id": payload.request_id,
                    "correlation_id": payload.correlation_id,
                    "turn_id": payload.turn_id,
                    "conversation_id": payload.conversation_id,
                    "message_id": payload.message_id,
                    "user_id": payload.user_id,
                    "capabilities": _json_payload(payload.capabilities),
                    "entitlements": _json_payload(payload.entitlements),
                    "provenance_json": _json_payload(payload.provenance_json),
                },
            )
            self._db_session.commit()
            return self._extract_out_int(plugin_invocation_id), self._extract_out_int(row_version)

    def _call_package(self, method_name: str, **kwargs: Any) -> int | None:
        """Call a package procedure using a narrow PL/SQL block."""
        if self._db_session is None:
            raise RuntimeError("Plugin audit DB session is unavailable.")

        block = self._build_block(method_name)
        with self._db_session.cursor() as cursor:
            bind_vars: dict[str, Any] = {}
            bind_vars["row_version"] = cursor.var(oracledb.NUMBER)
            for key, value in kwargs.items():
                if key in {"provenance_json", "event_payload_json"}:
                    bind_vars[key] = _json_payload(value)
                else:
                    bind_vars[key] = value
            cursor.execute(block, bind_vars)
            self._db_session.commit()
            row_version = bind_vars.get("row_version")
            if row_version is None:
                return None
            return self._extract_out_int(row_version)

    @staticmethod
    def _build_block(method_name: str) -> str:
        """Return the PL/SQL block used to call the package procedure."""
        if method_name == "record_policy_decision":
            return """
begin
  orac_code.plugin_audit_api.record_policy_decision(
    p_plugin_invocation_id => :plugin_invocation_id,
    p_policy_decision => :policy_decision,
    p_policy_reason => :policy_reason,
    p_event_message => :event_message,
    p_provenance_json => :provenance_json,
    p_row_version => :row_version
  );
end;
"""
        if method_name == "record_confirmation_event":
            return """
begin
  orac_code.plugin_audit_api.record_confirmation_event(
    p_plugin_invocation_id => :plugin_invocation_id,
    p_event_type => :event_type,
    p_confirmation_id => :confirmation_id,
    p_confirmation_status => :confirmation_status,
    p_event_message => :event_message,
    p_event_payload_json => :event_payload_json,
    p_row_version => :row_version
  );
end;
"""
        if method_name == "record_execution_event":
            return """
begin
  orac_code.plugin_audit_api.record_execution_event(
    p_plugin_invocation_id => :plugin_invocation_id,
    p_event_type => :event_type,
    p_execution_status => :execution_status,
    p_timeout_seconds => :timeout_seconds,
    p_failure_type => :failure_type,
    p_failure_message => :failure_message,
    p_provenance_json => :provenance_json,
    p_row_version => :row_version
  );
end;
"""
        if method_name == "link_message":
            return """
begin
  orac_code.plugin_audit_api.link_message(
    p_plugin_invocation_id => :plugin_invocation_id,
    p_message_id => :message_id,
    p_row_version => :row_version
  );
end;
"""
        raise ValueError(f"Unsupported plugin audit method '{method_name}'.")

    def _log_unavailable(self, stage: str) -> None:
        """Log that plugin audit persistence is unavailable."""
        if hasattr(self._logger, "log_warning"):
            self._logger.log_warning(
                f"Plugin audit persistence unavailable during {stage}; continuing without durable audit."
            )

    def _log_failure(self, stage: str, exc: BaseException) -> None:
        """Log a non-fatal plugin audit persistence failure."""
        message = f"Plugin audit persistence failed during {stage}: {exc}"
        if hasattr(self._logger, "log_error"):
            self._logger.log_error(message)
        elif hasattr(self._logger, "log_warning"):
            self._logger.log_warning(message)

    @staticmethod
    def _extract_out_int(value: Any) -> int | None:
        """Extract an integer from an Oracle OUT bind value."""
        raw = value.getvalue() if hasattr(value, "getvalue") else value
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        return _as_int(raw)
