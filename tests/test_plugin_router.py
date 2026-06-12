"""Tests for plugin execution orchestration."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Verifies that plugin routing candidates are executed outside the controller.

from __future__ import annotations

from pathlib import Path
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import sys
import time
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_router import PluginRouter
import model.plugin_router as plugin_router_module
from model.plugin_confirmation_broker import PluginConfirmationBroker
from model.plugin_execution_service import PluginExecutionService
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_routing.models import (
    PluginCandidate,
    PluginExecutionPolicy,
    PluginManifest,
)
from model.plugin_runtime import PluginExecutionResult


class _FakeLogger:
    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    def log_debug(self, message: str) -> None:
        self.messages.append(("debug", message))

    def log_info(self, message: str) -> None:
        self.messages.append(("info", message))

    def log_warning(self, message: str) -> None:
        self.messages.append(("warning", message))

    def log_error(self, message: str) -> None:
        self.messages.append(("error", message))


class _FakePluginManager:
    def __init__(self, manifest: PluginManifest | tuple[PluginManifest, ...] | None):
        if isinstance(manifest, tuple):
            self._manifests = {item.plugin_id: item for item in manifest}
        elif manifest is not None:
            self._manifests = {manifest.plugin_id: manifest}
        else:
            self._manifests = {}

    def get_manifest(self, plugin_id: str) -> PluginManifest | None:
        return self._manifests.get(plugin_id)


class _FakeRouter:
    def __init__(self, result: PluginExecutionResult | None):
        self.result = result
        self.calls: list[dict] = []

    def route(
        self,
        prompt: str,
        meta: dict,
        handoff: PluginRoutingHandoff | None,
        auth_user: str,
        *,
        audit_adapter=None,
        request_context=None,
    ) -> PluginExecutionResult | None:
        self.calls.append(
            {
                "prompt": prompt,
                "meta": meta,
                "handoff": handoff,
                "auth_user": auth_user,
                "audit_adapter": audit_adapter,
                "request_context": request_context,
            }
        )
        return self.result


class _FakeAuditSession:
    def __init__(self, payload: dict | None = None):
        self.payload = payload or {}
        self.plugin_invocation_id = 1
        self.row_version = None
        self.events: list[tuple[str, dict]] = []

    def record_policy_decision(
        self,
        *,
        policy_decision: str,
        policy_reason: str | None = None,
        event_message: str | None = None,
        provenance_json: dict | None = None,
    ) -> int | None:
        self.events.append(
            (
                "policy",
                {
                    "policy_decision": policy_decision,
                    "policy_reason": policy_reason,
                    "event_message": event_message,
                    "provenance_json": provenance_json,
                },
            )
        )
        return self.row_version

    def record_confirmation_event(
        self,
        *,
        event_type: str,
        confirmation_id: str | None,
        confirmation_status: str | None,
        event_message: str | None = None,
        event_payload_json: dict | None = None,
    ) -> int | None:
        self.events.append(
            (
                "confirmation",
                {
                    "event_type": event_type,
                    "confirmation_id": confirmation_id,
                    "confirmation_status": confirmation_status,
                    "event_message": event_message,
                    "event_payload_json": event_payload_json,
                },
            )
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
        provenance_json: dict | None = None,
    ) -> int | None:
        self.events.append(
            (
                "execution",
                {
                    "event_type": event_type,
                    "execution_status": execution_status,
                    "timeout_seconds": timeout_seconds,
                    "failure_type": failure_type,
                    "failure_message": failure_message,
                    "provenance_json": provenance_json,
                },
            )
        )
        return self.row_version


class _FakeAuditAdapter:
    def __init__(self):
        self.sessions: list[_FakeAuditSession] = []
        self.create_calls: list[dict] = []

    def create_session(
        self,
        *,
        provenance: dict,
        request_context: dict | None = None,
        policy_decision: str | None = None,
        confirmation_status: str | None = None,
        execution_status: str | None = None,
        timeout_seconds: float | None = None,
        failure_type: str | None = None,
        failure_message: str | None = None,
    ) -> _FakeAuditSession:
        self.create_calls.append(
            {
                "provenance": provenance,
                "request_context": request_context,
                "policy_decision": policy_decision,
                "confirmation_status": confirmation_status,
                "execution_status": execution_status,
                "timeout_seconds": timeout_seconds,
                "failure_type": failure_type,
                "failure_message": failure_message,
            }
        )
        session = _FakeAuditSession(payload=request_context)
        self.sessions.append(session)
        return session


class PluginExecutionServiceTests(unittest.TestCase):
    """Tests the controller-facing plugin execution service seam."""

    def test_service_returns_none_when_router_is_unavailable(self) -> None:
        logger = _FakeLogger()
        service = PluginExecutionService(plugin_router=None, logger=logger)

        result = service.execute(
            prompt="Hello",
            meta={},
            handoff=None,
            auth_user="unit_user",
        )

        self.assertIsNone(result)
        self.assertIn(
            (
                "debug",
                "Plugin execution unavailable; falling back to conversational flow.",
            ),
            logger.messages,
        )

    def test_service_delegates_to_router(self) -> None:
        handoff = PluginRoutingHandoff(
            candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
            refreshed=False,
        )
        expected = PluginExecutionResult(
            plugin_id="weather",
            content="Weather answer",
            provenance={"source": "plugin_execution", "plugin_id": "weather"},
        )
        router = _FakeRouter(expected)
        audit_adapter = object()
        service = PluginExecutionService(
            plugin_router=router,
            logger=_FakeLogger(),
            plugin_audit_adapter=audit_adapter,
        )

        result = service.execute(
            prompt="What's the weather?",
            meta={"client": "unit"},
            handoff=handoff,
            auth_user="unit_user",
            request_context={"request_id": "req-1"},
        )

        self.assertIs(result, expected)
        self.assertEqual(len(router.calls), 1)
        self.assertEqual(router.calls[0]["prompt"], "What's the weather?")
        self.assertEqual(router.calls[0]["handoff"], handoff)
        self.assertEqual(router.calls[0]["auth_user"], "unit_user")
        self.assertIs(router.calls[0]["audit_adapter"], audit_adapter)
        self.assertEqual(router.calls[0]["request_context"], {"request_id": "req-1"})

    def test_service_returns_none_for_unhandled_router_result(self) -> None:
        router = _FakeRouter(
            PluginExecutionResult(
                plugin_id="weather",
                content="Not handled",
                handled=False,
            )
        )
        service = PluginExecutionService(plugin_router=router, logger=_FakeLogger())

        result = service.execute(
            prompt="Hello",
            meta={},
            handoff=None,
            auth_user="unit_user",
        )

        self.assertIsNone(result)

    def test_service_adds_legacy_provenance_fallback(self) -> None:
        router = _FakeRouter(
            PluginExecutionResult(
                plugin_id="weather",
                content="Weather answer",
                provenance={},
            )
        )
        service = PluginExecutionService(plugin_router=router, logger=_FakeLogger())

        result = service.execute(
            prompt="What's the weather?",
            meta={},
            handoff=None,
            auth_user="unit_user",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["source"], "plugin_execution")
        self.assertEqual(result.provenance["plugin_id"], "weather")
        self.assertEqual(result.provenance["status"], "allowed")


class PluginRouterTests(unittest.TestCase):
    """Tests the dedicated plugin execution orchestrator."""

    def _manifest(
        self,
        *,
        plugin_id: str = "weather",
        name: str = "Weather",
        action_type: str = "informational_read_only",
        requires_confirmation: bool = False,
        allowed_by_default: bool = True,
        scaffold: bool = False,
        description: str = "Weather plugin",
        capabilities: tuple[str, ...] | None = None,
        entities: tuple[str, ...] = (),
        examples: tuple[str, ...] = (),
    ) -> PluginManifest:
        manifest_capabilities = capabilities or (f"{plugin_id}.current_conditions",)
        return PluginManifest(
            schema_version=2,
            plugin_id=plugin_id,
            name=name,
            description=description,
            version="1.0.0",
            enabled=True,
            capabilities=manifest_capabilities,
            entitlements=(),
            entities=entities,
            examples=examples,
            entry_point="plugin:Plugin",
            manifest_path=Path(f"plugins/{plugin_id}.json"),
            plugin_dir=Path(f"plugins/{plugin_id}"),
            manifest_hash="abc123",
            runtime_mode="on_demand",
            execution_policy=PluginExecutionPolicy(
                action_type=action_type,
                requires_confirmation=requires_confirmation,
                allowed_by_default=allowed_by_default,
                capabilities=manifest_capabilities,
                scaffold=scaffold,
            ),
        )

    def _home_assistant_manifest(self, *, scaffold: bool = False) -> PluginManifest:
        return self._manifest(
            plugin_id="home_assistant",
            name="Home Assistant",
            action_type="device_control",
            requires_confirmation=True,
            allowed_by_default=False,
            scaffold=scaffold,
            description="Home automation device control for lights and switches.",
            capabilities=("home_assistant.device_control",),
            entities=("lights", "switches", "kitchen", "lounge"),
            examples=("Turn on the kitchen lights.",),
        )

    def _media_control_manifest(self) -> PluginManifest:
        return self._manifest(
            plugin_id="media_control",
            name="Media Control",
            action_type="privileged_system_action",
            requires_confirmation=True,
            allowed_by_default=False,
            description="Control local media playback devices.",
            capabilities=("media_control.playback_control",),
            entities=("tv", "speaker", "volume", "playlist", "lounge"),
            examples=("Pause the lounge TV.", "Turn the volume down."),
        )

    def test_router_returns_first_handled_result(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        class _HandlingPlugin:
            def __init__(self, logger, config_mgr):
                self.logger = logger
                self.config_mgr = config_mgr

            def can_handle(self, prompt: str) -> bool:
                return True

            def execute(self, prompt: str, meta: dict):
                return PluginExecutionResult(plugin_id="weather", content="Direct weather answer")

        original_loader = plugin_router_module.load_plugin_class
        plugin_router_module.load_plugin_class = lambda loaded_manifest: _HandlingPlugin
        try:
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )
        finally:
            plugin_router_module.load_plugin_class = original_loader

        self.assertIsNotNone(result)
        self.assertEqual(result.plugin_id, "weather")
        self.assertEqual(result.content, "Direct weather answer")
        self.assertEqual(result.provenance["source"], "plugin_execution")
        self.assertEqual(result.provenance["plugin_id"], "weather")
        self.assertEqual(result.provenance["action_type"], "informational_read_only")
        self.assertEqual(result.provenance["status"], "allowed")

    def test_router_records_audit_events_for_handled_plugin(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest()
        audit_adapter = _FakeAuditAdapter()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        class _HandlingPlugin:
            def __init__(self, logger, config_mgr):
                self.logger = logger
                self.config_mgr = config_mgr

            def can_handle(self, prompt: str) -> bool:
                return True

            def execute(self, prompt: str, meta: dict):
                return PluginExecutionResult(plugin_id="weather", content="Direct weather answer")

        original_loader = plugin_router_module.load_plugin_class
        plugin_router_module.load_plugin_class = lambda loaded_manifest: _HandlingPlugin
        try:
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
                audit_adapter=audit_adapter,
                request_context={"request_id": "req-1", "turn_id": "turn-1"},
            )
        finally:
            plugin_router_module.load_plugin_class = original_loader

        self.assertIsNotNone(result)
        self.assertEqual(result.plugin_id, "weather")
        self.assertEqual(len(audit_adapter.sessions), 1)
        self.assertEqual(audit_adapter.create_calls[0]["request_context"]["request_id"], "req-1")
        self.assertTrue(
            any(
                event[0] == "policy" and event[1]["policy_decision"] == "allowed"
                for event in audit_adapter.sessions[0].events
            )
        )
        self.assertTrue(
            any(
                event[0] == "execution" and event[1]["event_type"] == "execution_started"
                for event in audit_adapter.sessions[0].events
            )
        )
        self.assertTrue(
            any(event[1]["event_type"] == "execution_completed" for event in audit_adapter.sessions[0].events if event[0] == "execution")
        )

    def test_router_records_audit_event_for_declined_can_handle(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest()
        audit_adapter = _FakeAuditAdapter()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        class _DecliningPlugin:
            def __init__(self, logger, config_mgr):
                self.logger = logger
                self.config_mgr = config_mgr

            def can_handle(self, prompt: str) -> bool:
                return False

            def execute(self, prompt: str, meta: dict):
                raise AssertionError("declined plugin must not execute")

        original_loader = plugin_router_module.load_plugin_class
        plugin_router_module.load_plugin_class = lambda loaded_manifest: _DecliningPlugin
        try:
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
                audit_adapter=audit_adapter,
                request_context={"request_id": "req-3", "turn_id": "turn-3"},
            )
        finally:
            plugin_router_module.load_plugin_class = original_loader

        self.assertIsNone(result)
        self.assertEqual(len(audit_adapter.sessions), 1)
        self.assertTrue(
            any(
                event[0] == "execution"
                and event[1]["event_type"] == "execution_failed"
                and event[1]["execution_status"] == "denied"
                and event[1]["failure_type"] == "can_handle_declined"
                for event in audit_adapter.sessions[0].events
            )
        )

    def test_declined_matching_mutation_does_not_fall_through_to_llm(self) -> None:
        manifest = self._manifest(
            plugin_id="home_assistant",
            action_type="device_control",
            capabilities=("home_assistant.device_control",),
            entities=("light", "lamp", "switch"),
        )
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=_FakeLogger(),
            config_mgr=object(),
            context_manager=object(),
        )

        class _DecliningPlugin:
            def can_handle(self, prompt: str) -> bool:
                return False

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            return_value=_DecliningPlugin,
        ):
            for prompt in (
                "Switch off the desk lamp.",
                "Switch office lamp off.",
            ):
                with self.subTest(prompt=prompt):
                    result = router.route(
                        prompt,
                        {},
                        PluginRoutingHandoff(
                            candidates=(
                                PluginCandidate(plugin_id="home_assistant", score=0.91),
                            ),
                            refreshed=False,
                        ),
                        auth_user="unit_user",
                    )

                    self.assertIsNotNone(result)
                    self.assertEqual(result.plugin_id, "home_assistant")
                    self.assertEqual(result.provenance["status"], "failed")
                    self.assertEqual(
                        result.provenance["failure_type"],
                        "can_handle_declined",
                    )

    def test_router_records_audit_event_for_load_failure(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest()
        audit_adapter = _FakeAuditAdapter()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("load failure"),
        ):
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
                audit_adapter=audit_adapter,
                request_context={"request_id": "req-4", "turn_id": "turn-4"},
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "failed")
        self.assertEqual(len(audit_adapter.sessions), 1)
        self.assertTrue(
            any(
                event[0] == "execution"
                and event[1]["event_type"] == "execution_failed"
                and event[1]["execution_status"] == "failed"
                and event[1]["failure_type"] == "AssertionError"
                for event in audit_adapter.sessions[0].events
            )
        )

    def test_router_records_audit_event_for_instantiate_failure(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest()
        audit_adapter = _FakeAuditAdapter()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        class _BrokenPlugin:
            def __init__(self, logger, config_mgr):
                raise RuntimeError("instantiate failure")

        with patch.object(plugin_router_module, "load_plugin_class", return_value=_BrokenPlugin):
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
                audit_adapter=audit_adapter,
                request_context={"request_id": "req-5", "turn_id": "turn-5"},
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "failed")
        self.assertEqual(len(audit_adapter.sessions), 1)
        self.assertTrue(
            any(
                event[0] == "execution"
                and event[1]["event_type"] == "execution_failed"
                and event[1]["execution_status"] == "failed"
                and event[1]["failure_type"] == "RuntimeError"
                for event in audit_adapter.sessions[0].events
            )
        )

    def test_router_records_audit_events_for_denied_plugin(self) -> None:
        logger = _FakeLogger()
        manifest = self._home_assistant_manifest(scaffold=True)
        audit_adapter = _FakeAuditAdapter()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("blocked plugin code must not be imported"),
        ):
            result = router.route(
                "Turn on the kitchen lights.",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="home_assistant", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
                audit_adapter=audit_adapter,
                request_context={"request_id": "req-2", "turn_id": "turn-2"},
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "denied")
        self.assertEqual(len(audit_adapter.sessions), 1)
        self.assertTrue(
            any(
                event[0] == "policy" and event[1]["policy_decision"] == "denied"
                for event in audit_adapter.sessions[0].events
            )
        )

    def test_router_blocks_device_control_without_confirmation(self) -> None:
        logger = _FakeLogger()
        manifest = self._home_assistant_manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
            confirmation_broker=PluginConfirmationBroker(
                token_factory=lambda: "confirm-ha",
            ),
        )

        result = router.route(
            "Turn on the kitchen lights.",
            {},
            PluginRoutingHandoff(
                candidates=(PluginCandidate(plugin_id="home_assistant", score=0.91),),
                refreshed=False,
            ),
            auth_user="unit_user",
        )

        self.assertIsNotNone(result)
        self.assertIn("needs explicit confirmation", result.content)
        self.assertEqual(result.provenance["status"], "requires_confirmation")
        self.assertEqual(result.provenance["action_type"], "device_control")
        self.assertIn("confirmation_request", result.provenance)
        self.assertEqual(
            result.provenance["confirmation_request"]["confirmation_id"],
            "confirm-ha",
        )

    def test_confirmation_required_plugin_does_not_import_plugin_code(self) -> None:
        logger = _FakeLogger()
        manifest = self._home_assistant_manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("blocked plugin code must not be imported"),
        ):
            result = router.route(
                "Turn on the kitchen lights.",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="home_assistant", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "requires_confirmation")

    def test_arbitrary_request_metadata_is_not_trusted_confirmation(self) -> None:
        logger = _FakeLogger()
        manifest = self._media_control_manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
            confirmation_broker=PluginConfirmationBroker(token_factory=lambda: "confirm-1"),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("request metadata must not authorize import"),
        ):
            result = router.route(
                "Pause the lounge TV.",
                {"plugin_policy": {"allow_risky_actions": True, "confirmed": True}},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="media_control", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "requires_confirmation")
        self.assertEqual(
            result.provenance["confirmation_request"]["confirmation_id"],
            "confirm-1",
        )

    def test_router_fails_safe_for_unknown_action_type(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest(action_type="unknown_action")
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        result = router.route(
            "Run the Weather plugin.",
            {},
            PluginRoutingHandoff(
                candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                refreshed=False,
            ),
            auth_user="unit_user",
        )

        self.assertIsNotNone(result)
        self.assertIn("not allowed", result.content)
        self.assertEqual(result.provenance["status"], "denied")
        self.assertIn("Unknown plugin action type", result.provenance["reason"])

    def test_unknown_action_type_does_not_import_plugin_code(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest(action_type="unknown_action")
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("unknown action plugin code must not be imported"),
        ):
            result = router.route(
                "Run the Weather plugin.",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "denied")

    def test_router_denies_scaffold_home_assistant_before_plugin_load(self) -> None:
        logger = _FakeLogger()
        manifest = self._home_assistant_manifest(scaffold=True)
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        result = router.route(
            "Turn on the kitchen lights.",
            {"plugin_policy": {"allow_risky_actions": True, "confirmed": True}},
            PluginRoutingHandoff(
                candidates=(PluginCandidate(plugin_id="home_assistant", score=0.91),),
                refreshed=False,
            ),
            auth_user="unit_user",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "denied")
        self.assertTrue(result.provenance["scaffold"])

    def test_scaffold_plugin_does_not_import_even_with_confirmation_metadata(self) -> None:
        logger = _FakeLogger()
        manifest = self._home_assistant_manifest(scaffold=True)
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("scaffold plugin code must not be imported"),
        ):
            result = router.route(
                "Turn on the kitchen lights.",
                {"plugin_policy": {"allow_risky_actions": True, "confirmed": True}},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="home_assistant", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "denied")
        self.assertTrue(result.provenance["scaffold"])

    def test_unmatched_risky_candidate_does_not_hijack_conversation(self) -> None:
        logger = _FakeLogger()
        manifest = self._media_control_manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("unmatched risky plugin code must not be imported"),
        ):
            result = router.route(
                "What time is it?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="media_control", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNone(result)
        self.assertIn(
            (
                "debug",
                "Plugin execution denial skipped for 'media_control' because the prompt did not "
                "match manifest-declared routing terms.",
            ),
            logger.messages,
        )

    def test_natural_history_question_does_not_trigger_media_confirmation(self) -> None:
        logger = _FakeLogger()
        manifest = self._media_control_manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("factual question must not import media plugin code"),
        ):
            result = router.route(
                "When the meteorite struck earth and wiped out the dinosaurs, "
                "did any of them die of a heart attack?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="media_control", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNone(result)
        self.assertIn(
            (
                "debug",
                "Plugin execution denial skipped for 'media_control' because the prompt did not "
                "match manifest-declared routing terms.",
            ),
            logger.messages,
        )

    def test_factual_question_with_media_term_does_not_trigger_confirmation(self) -> None:
        logger = _FakeLogger()
        manifest = self._media_control_manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("factual question must not import media plugin code"),
        ):
            result = router.route(
                "What is the volume of a dinosaur's heart?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="media_control", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNone(result)
        self.assertIn(
            (
                "debug",
                "Plugin execution denial skipped for 'media_control' because the prompt matched "
                "manifest terms but did not contain an explicit action intent.",
            ),
            logger.messages,
        )

    def test_factual_question_with_media_action_word_does_not_trigger_confirmation(self) -> None:
        logger = _FakeLogger()
        manifest = self._media_control_manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("factual question must not import media plugin code"),
        ):
            result = router.route(
                "Did the lounge playlist stop when dinosaurs died of a heart attack?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="media_control", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNone(result)
        self.assertIn(
            (
                "debug",
                "Plugin execution denial skipped for 'media_control' because the prompt matched "
                "manifest terms but did not contain an explicit action intent.",
            ),
            logger.messages,
        )

    def test_unmatched_risky_candidate_falls_through_to_safe_plugin(self) -> None:
        logger = _FakeLogger()
        media_manifest = self._media_control_manifest()
        weather_manifest = self._manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager((media_manifest, weather_manifest)),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        class _HandlingWeatherPlugin:
            def can_handle(self, prompt: str) -> bool:
                return "weather" in prompt.lower()

            def execute(self, prompt: str, meta: dict):
                del prompt, meta
                return PluginExecutionResult(plugin_id="weather", content="Weather answer")

        loaded_plugin_ids: list[str] = []

        def _load_plugin(loaded_manifest: PluginManifest):
            loaded_plugin_ids.append(loaded_manifest.plugin_id)
            if loaded_manifest.plugin_id == "media_control":
                raise AssertionError("unmatched risky plugin code must not be imported")
            return _HandlingWeatherPlugin

        with patch.object(plugin_router_module, "load_plugin_class", side_effect=_load_plugin):
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(
                        PluginCandidate(plugin_id="media_control", score=0.91),
                        PluginCandidate(plugin_id="weather", score=0.72),
                    ),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.plugin_id, "weather")
        self.assertEqual(result.content, "Weather answer")
        self.assertEqual(loaded_plugin_ids, ["weather"])

    def test_matched_risky_candidate_is_still_denied_before_import(self) -> None:
        logger = _FakeLogger()
        manifest = self._media_control_manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("matched risky plugin code must not be imported"),
        ):
            result = router.route(
                "Pause the lounge TV.",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="media_control", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertIn("needs explicit confirmation", result.content)
        self.assertEqual(result.provenance["status"], "requires_confirmation")
        self.assertEqual(result.provenance["action_type"], "privileged_system_action")

    def test_broker_issued_confirmation_allows_matched_risky_candidate(self) -> None:
        logger = _FakeLogger()
        manifest = self._media_control_manifest()
        broker = PluginConfirmationBroker(token_factory=lambda: "confirm-allow")
        confirmation = broker.create_request(manifest, manifest.execution_policy)
        broker.confirm_request(confirmation.confirmation_id)
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
            confirmation_broker=broker,
        )

        class _HandlingPlugin:
            def can_handle(self, prompt: str) -> bool:
                return True

            def execute(self, prompt: str, meta: dict):
                del prompt, meta
                return PluginExecutionResult(
                    plugin_id="media_control",
                    content="Paused.",
                )

        with patch.object(plugin_router_module, "load_plugin_class", return_value=_HandlingPlugin):
            result = router.route(
                "Pause the lounge TV.",
                {"plugin_confirmation": {"confirmation_id": confirmation.confirmation_id}},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="media_control", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.content, "Paused.")
        self.assertEqual(result.provenance["status"], "allowed")
        self.assertTrue(result.provenance["confirmation"]["trusted"])
        self.assertEqual(
            result.provenance["confirmation"]["confirmation_id"],
            "confirm-allow",
        )

    def test_scaffold_denial_overrides_broker_confirmation(self) -> None:
        logger = _FakeLogger()
        manifest = self._home_assistant_manifest(scaffold=True)
        broker = PluginConfirmationBroker(token_factory=lambda: "confirm-scaffold")
        confirmation = broker.create_request(manifest, manifest.execution_policy)
        broker.confirm_request(confirmation.confirmation_id)
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
            confirmation_broker=broker,
        )

        with patch.object(
            plugin_router_module,
            "load_plugin_class",
            side_effect=AssertionError("scaffold plugin code must not be imported"),
        ):
            result = router.route(
                "Turn on the kitchen lights.",
                {"plugin_confirmation": {"confirmation_id": confirmation.confirmation_id}},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="home_assistant", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["status"], "denied")
        self.assertTrue(result.provenance["scaffold"])

    def test_plugin_supplied_provenance_cannot_override_core_policy(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        class _HandlingPlugin:
            def execute(self, prompt: str, meta: dict):
                del prompt, meta
                return PluginExecutionResult(
                    plugin_id="weather",
                    content="Direct weather answer",
                    provenance={
                        "source": "plugin_execution",
                        "plugin_id": "other",
                        "action_type": "device_control",
                        "status": "denied",
                    },
                )

        with patch.object(plugin_router_module, "load_plugin_class", return_value=_HandlingPlugin):
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.provenance["plugin_id"], "weather")
        self.assertEqual(result.provenance["action_type"], "informational_read_only")
        self.assertEqual(result.provenance["status"], "allowed")

    def test_plugin_exception_returns_failed_plugin_provenance(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        class _FailingPlugin:
            def can_handle(self, prompt: str) -> bool:
                return True

            def execute(self, prompt: str, meta: dict):
                del prompt, meta
                raise RuntimeError("provider unavailable with diagnostic detail")

        with patch.object(plugin_router_module, "load_plugin_class", return_value=_FailingPlugin):
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.plugin_id, "weather")
        self.assertEqual(result.content, "Weather could not complete the request.")
        self.assertEqual(result.provenance["source"], "plugin_execution")
        self.assertEqual(result.provenance["status"], "failed")
        self.assertEqual(result.provenance["policy_decision"], "allowed")
        self.assertEqual(result.provenance["failure_type"], "RuntimeError")
        self.assertEqual(result.provenance["failure_message"], "Plugin execution failed during execute.")
        self.assertNotIn("provider unavailable", result.content)
        self.assertIn(
            (
                "error",
                "Plugin execution failed for 'weather' during execute (non-fatal): "
                "provider unavailable with diagnostic detail",
            ),
            logger.messages,
        )

    def test_plugin_timeout_returns_timed_out_plugin_provenance(self) -> None:
        logger = _FakeLogger()
        manifest = self._manifest()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
            execution_timeout_seconds=0.01,
        )

        class _SlowPlugin:
            def can_handle(self, prompt: str) -> bool:
                return True

            def execute(self, prompt: str, meta: dict):
                del prompt, meta
                time.sleep(0.05)
                return PluginExecutionResult(plugin_id="weather", content="Late answer")

        with patch.object(plugin_router_module, "load_plugin_class", return_value=_SlowPlugin):
            result = router.route(
                "What's the weather in London?",
                {},
                PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="weather", score=0.91),),
                    refreshed=False,
                ),
                auth_user="unit_user",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result.plugin_id, "weather")
        self.assertEqual(result.content, "Weather timed out before completing the request.")
        self.assertEqual(result.provenance["source"], "plugin_execution")
        self.assertEqual(result.provenance["status"], "timed_out")
        self.assertEqual(result.provenance["policy_decision"], "allowed")
        self.assertEqual(result.provenance["failure_type"], "timeout")
        self.assertEqual(result.provenance["timeout_seconds"], 0.01)
        self.assertIn(
            (
                "error",
                "Plugin execution timed out for 'weather' after 0.010s.",
            ),
            logger.messages,
        )

    def test_router_falls_back_when_no_plugin_handles(self) -> None:
        logger = _FakeLogger()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(None),
            logger=logger,
            config_mgr=object(),
            context_manager=object(),
        )

        result = router.route(
            "Hello there",
            {},
            PluginRoutingHandoff(
                candidates=(PluginCandidate(plugin_id="weather", score=0.80),),
                refreshed=False,
            ),
            auth_user="unit_user",
        )

        self.assertIsNone(result)
        self.assertIn(
            ("debug", "No plugin candidate handled the request directly; falling back to conversational flow."),
            logger.messages,
        )


class PluginConfirmationBrokerTests(unittest.TestCase):
    """Tests the trusted plugin confirmation state seam."""

    def _manifest(self) -> PluginManifest:
        return PluginRouterTests()._media_control_manifest()

    def test_confirmation_request_records_plugin_action_metadata(self) -> None:
        manifest = self._manifest()
        broker = PluginConfirmationBroker(token_factory=lambda: "confirm-123")

        request = broker.create_request(
            manifest,
            manifest.execution_policy,
            action_summary="Pause the lounge TV.",
        )

        self.assertEqual(request.confirmation_id, "confirm-123")
        self.assertEqual(request.plugin_id, "media_control")
        self.assertEqual(request.plugin_name, "Media Control")
        self.assertEqual(request.action_type, "privileged_system_action")
        self.assertEqual(request.capabilities, ("media_control.playback_control",))
        self.assertEqual(request.action_summary, "Pause the lounge TV.")

    def test_confirmation_decision_expires(self) -> None:
        now = datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)

        def _clock() -> datetime:
            return now

        manifest = self._manifest()
        broker = PluginConfirmationBroker(
            ttl_seconds=5,
            now=_clock,
            token_factory=lambda: "confirm-expire",
        )
        request = broker.create_request(manifest, manifest.execution_policy)
        broker.confirm_request(request.confirmation_id)
        now = now + timedelta(seconds=6)

        decision = broker.consume_confirmation(
            confirmation_id=request.confirmation_id,
            manifest=manifest,
            policy=manifest.execution_policy,
        )

        self.assertFalse(decision.confirmed)
        self.assertEqual(decision.status, "expired")

    def test_confirmation_decision_cannot_be_reused(self) -> None:
        manifest = self._manifest()
        broker = PluginConfirmationBroker(token_factory=lambda: "confirm-once")
        request = broker.create_request(manifest, manifest.execution_policy)
        broker.confirm_request(request.confirmation_id)

        first_decision = broker.consume_confirmation(
            confirmation_id=request.confirmation_id,
            manifest=manifest,
            policy=manifest.execution_policy,
        )
        second_decision = broker.consume_confirmation(
            confirmation_id=request.confirmation_id,
            manifest=manifest,
            policy=manifest.execution_policy,
        )

        self.assertTrue(first_decision.confirmed)
        self.assertFalse(second_decision.confirmed)
        self.assertEqual(second_decision.status, "replayed")


if __name__ == "__main__":
    unittest.main()
