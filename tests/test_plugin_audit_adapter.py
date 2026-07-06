"""Tests for runtime plugin audit payloads and adapter behaviour."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Verifies plugin audit payload normalisation, best-effort DB
#   fallback, and the absence of direct plugin-side audit writes.

from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if "oracledb" not in sys.modules:
    import types

    stub_oracledb = types.ModuleType("oracledb")
    stub_oracledb.NUMBER = object()
    sys.modules["oracledb"] = stub_oracledb

from model.plugin_audit_adapter import PluginAuditAdapter
from model.plugin_audit_adapter import PluginAuditPayload


class _FakeLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def log_debug(self, message: str) -> None:
        self.messages.append(("debug", message))

    def log_info(self, message: str) -> None:
        self.messages.append(("info", message))

    def log_warning(self, message: str) -> None:
        self.messages.append(("warning", message))

    def log_error(self, message: str) -> None:
        self.messages.append(("error", message))


class _FailingCursor:
    def __enter__(self) -> "_FailingCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def var(self, *_args, **_kwargs):
        return object()

    def execute(self, *_args, **_kwargs) -> None:
        raise RuntimeError("database unavailable")


class _FailingDBSession:
    def cursor(self) -> _FailingCursor:
        return _FailingCursor()

    def commit(self) -> None:
        return None


class _OutVar:
    def __init__(self, value: int) -> None:
        self._value = value

    def getvalue(self) -> int:
        return self._value


class _RecordingCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []

    def __enter__(self) -> "_RecordingCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def var(self, *_args, **_kwargs) -> _OutVar:
        return _OutVar(1)

    def execute(self, block: str, binds: dict) -> None:
        self.executed.append((block, binds))


class _RecordingDBSession:
    def __init__(self) -> None:
        self.cursor_obj = _RecordingCursor()
        self.commits = 0

    def cursor(self) -> _RecordingCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.commits += 1


class PluginAuditPayloadTests(unittest.TestCase):
    """Tests plugin audit payload normalisation from provenance."""

    def test_completed_provenance_normalises_to_payload(self) -> None:
        provenance = {
            "source": "plugin_execution",
            "plugin_id": "weather",
            "plugin_name": "Weather",
            "action_type": "informational_read_only",
            "status": "allowed",
            "capabilities": ("weather.current_conditions",),
            "entitlements": ("user_preferences.user_location",),
        }

        payload = PluginAuditPayload.from_provenance(
            provenance,
            request_context={
                "request_id": "req-1",
                "correlation_id": "corr-1",
                "turn_id": "turn-1",
                "conversation_id": 101,
                "message_id": 202,
                "user_id": 303,
            },
            policy_decision="allowed",
            execution_status="completed",
        )

        self.assertEqual(payload.request_id, "req-1")
        self.assertEqual(payload.correlation_id, "corr-1")
        self.assertEqual(payload.turn_id, "turn-1")
        self.assertEqual(payload.conversation_id, 101)
        self.assertEqual(payload.message_id, 202)
        self.assertEqual(payload.user_id, 303)
        self.assertEqual(payload.plugin_id, "weather")
        self.assertEqual(payload.plugin_name, "Weather")
        self.assertEqual(payload.action_type, "informational_read_only")
        self.assertEqual(payload.policy_decision, "allowed")
        self.assertEqual(payload.execution_status, "completed")
        self.assertEqual(payload.capabilities, ("weather.current_conditions",))
        self.assertEqual(payload.entitlements, ("user_preferences.user_location",))

    def test_policy_outcomes_normalise_to_payload(self) -> None:
        cases = [
            (
                "denied",
                "denied",
                {
                    "source": "plugin_execution",
                    "plugin_id": "home_assistant",
                    "plugin_name": "Home Assistant",
                    "action_type": "device_control",
                    "status": "denied",
                    "reason": "Plugin is marked scaffold or experimental and is not control-capable.",
                },
            ),
            (
                "requires_confirmation",
                "requires_confirmation",
                {
                    "source": "plugin_execution",
                    "plugin_id": "media_control",
                    "plugin_name": "Media Control",
                    "action_type": "privileged_system_action",
                    "status": "requires_confirmation",
                    "confirmation_request": {
                        "confirmation_id": "confirm-1",
                        "status": "issued",
                    },
                },
            ),
            (
                "scaffold",
                "denied",
                {
                    "source": "plugin_execution",
                    "plugin_id": "home_assistant",
                    "plugin_name": "Home Assistant",
                    "action_type": "device_control",
                    "status": "denied",
                    "scaffold": True,
                },
            ),
            (
                "unknown",
                "denied",
                {
                    "source": "plugin_execution",
                    "plugin_id": "weather",
                    "plugin_name": "Weather",
                    "action_type": "unknown_action",
                    "status": "denied",
                    "reason": "Unknown plugin action type 'unknown_action'.",
                },
            ),
        ]

        for label, expected_execution_status, provenance in cases:
            with self.subTest(label=label):
                payload = PluginAuditPayload.from_provenance(
                    provenance,
                    request_context={"request_id": "req-2"},
                )
                self.assertEqual(payload.plugin_id, provenance["plugin_id"])
                self.assertEqual(payload.plugin_name, provenance["plugin_name"])
                self.assertEqual(payload.action_type, provenance["action_type"])
                self.assertEqual(payload.policy_decision, provenance["status"])
                self.assertEqual(payload.execution_status, expected_execution_status)

    def test_failure_and_timeout_provenance_normalise_to_payload(self) -> None:
        failure_provenance = {
            "source": "plugin_execution",
            "plugin_id": "weather",
            "plugin_name": "Weather",
            "action_type": "informational_read_only",
            "status": "failed",
            "policy_decision": "allowed",
            "failure_type": "RuntimeError",
            "failure_message": "Plugin execution failed during execute.",
        }
        timeout_provenance = {
            "source": "plugin_execution",
            "plugin_id": "weather",
            "plugin_name": "Weather",
            "action_type": "informational_read_only",
            "status": "timed_out",
            "policy_decision": "allowed",
            "failure_type": "timeout",
            "failure_message": "Plugin execution exceeded the configured timeout of 0.010 seconds.",
            "timeout_seconds": 0.01,
        }

        failure_payload = PluginAuditPayload.from_provenance(
            failure_provenance,
            request_context={"request_id": "req-3"},
        )
        timeout_payload = PluginAuditPayload.from_provenance(
            timeout_provenance,
            request_context={"request_id": "req-4"},
        )

        self.assertEqual(failure_payload.execution_status, "failed")
        self.assertEqual(failure_payload.policy_decision, "allowed")
        self.assertEqual(failure_payload.failure_type, "RuntimeError")
        self.assertEqual(failure_payload.failure_message, "Plugin execution failed during execute.")
        self.assertEqual(timeout_payload.execution_status, "timed_out")
        self.assertEqual(timeout_payload.policy_decision, "allowed")
        self.assertEqual(timeout_payload.timeout_seconds, 0.01)
        self.assertEqual(timeout_payload.failure_type, "timeout")


class PluginAuditAdapterTests(unittest.TestCase):
    """Tests the runtime adapter's best-effort behaviour."""

    def test_begin_invocation_converts_json_text_binds_in_plsql(self) -> None:
        db_session = _RecordingDBSession()
        adapter = PluginAuditAdapter(db_session=db_session, logger=_FakeLogger())

        session = adapter.create_session(
            provenance={
                "plugin_id": "weather",
                "plugin_name": "Weather",
                "action_type": "informational_read_only",
                "status": "allowed",
                "capabilities": ("weather.current_conditions",),
                "entitlements": ("user_preferences.user_location",),
            },
            request_context={"request_id": "req-5"},
        )

        self.assertEqual(session.plugin_invocation_id, 1)
        block, binds = db_session.cursor_obj.executed[0]
        self.assertIn("l_capabilities := json(:capabilities);", block)
        self.assertIn("l_entitlements := json(:entitlements);", block)
        self.assertIn("l_provenance_json := json(:provenance_json);", block)
        self.assertIn("p_capabilities => l_capabilities", block)
        self.assertIsInstance(binds["capabilities"], str)
        self.assertIsInstance(binds["entitlements"], str)
        self.assertIsInstance(binds["provenance_json"], str)

    def test_audit_adapter_failure_does_not_break_best_effort_execution(self) -> None:
        logger = _FakeLogger()
        adapter = PluginAuditAdapter(db_session=_FailingDBSession(), logger=logger)

        session = adapter.create_session(
            provenance={
                "plugin_id": "weather",
                "plugin_name": "Weather",
                "action_type": "informational_read_only",
                "status": "allowed",
            },
            request_context={"request_id": "req-5"},
        )

        self.assertIsNotNone(session)
        self.assertIsNone(session.plugin_invocation_id)
        self.assertTrue(any(level == "error" for level, _message in logger.messages))

    def test_replacing_db_session_routes_future_writes_to_new_session(self) -> None:
        stale_session = _RecordingDBSession()
        current_session = _RecordingDBSession()
        adapter = PluginAuditAdapter(db_session=stale_session, logger=_FakeLogger())

        adapter.set_db_session(current_session)
        session = adapter.create_session(
            provenance={
                "plugin_id": "home_assistant",
                "plugin_name": "Home Assistant",
                "action_type": "metadata_synchronisation",
                "status": "allowed",
            },
            request_context={"request_id": "req-resync"},
        )

        self.assertEqual(session.plugin_invocation_id, 1)
        self.assertEqual(stale_session.cursor_obj.executed, [])
        self.assertEqual(len(current_session.cursor_obj.executed), 1)

    def test_plugins_do_not_write_audit_records_directly(self) -> None:
        plugin_root = PROJECT_ROOT / "plugins"
        forbidden_tokens = (
            "plugin_audit_api",
            "plugin_invocations",
            "plugin_audit_events",
        )
        matches: list[str] = []

        for path in plugin_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".json", ".md", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            if any(token in text for token in forbidden_tokens):
                matches.append(str(path.relative_to(PROJECT_ROOT)))

        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
