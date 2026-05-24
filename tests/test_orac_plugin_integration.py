"""Tests the Orac integration seam for plugin routing candidate retrieval."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Verifies startup/bootstrap guards and request-flow handoff formatting for plugin routing.

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if "langchain_openai" not in sys.modules:
    stub_module = types.ModuleType("langchain_openai")

    class _StubChatOpenAI:  # pragma: no cover - import shim for test isolation
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def invoke(self, prompt):
            return prompt

    stub_module.ChatOpenAI = _StubChatOpenAI
    sys.modules["langchain_openai"] = stub_module

if "oracledb" not in sys.modules:
    stub_oracledb = types.ModuleType("oracledb")

    class _StubConnection:
        pass

    class _StubDatabaseError(Exception):
        pass

    stub_oracledb.Connection = _StubConnection
    stub_oracledb.DatabaseError = _StubDatabaseError
    stub_oracledb.NUMBER = object()
    sys.modules["oracledb"] = stub_oracledb

import controller.orac as orac_module
from controller.orac import Orac
from model.plugin_routing import render_plugin_routing_hints
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_routing.models import (
    PluginCandidate,
    PluginHealthCheck,
    PluginManifest,
    PluginServiceRuntime,
)


def _manifest(
    plugin_id: str,
    *,
    runtime_mode: str = "on_demand",
    enabled: bool = True,
    start_policy: str = "manual",
) -> PluginManifest:
    service_runtime = None
    if runtime_mode in {"service", "hybrid"}:
        service_runtime = PluginServiceRuntime(
            entry_point="plugin:TestService",
            execution_model="long_running",
            start_policy=start_policy,
            restart_policy="never",
            shutdown_timeout_seconds=1,
            health_check=PluginHealthCheck(enabled=False),
        )
    return PluginManifest(
        schema_version=2,
        plugin_id=plugin_id,
        name=plugin_id.replace("_", " ").title(),
        description="Test plugin.",
        version="1.0.0",
        enabled=enabled,
        capabilities=(f"{plugin_id}.capability",),
        entitlements=(),
        entities=(),
        examples=(),
        entry_point="plugin:TestPlugin",
        manifest_path=PROJECT_ROOT / "plugins" / f"{plugin_id}.json",
        plugin_dir=PROJECT_ROOT / "plugins" / plugin_id,
        manifest_hash=f"{plugin_id}-hash",
        runtime_mode=runtime_mode,
        service_runtime=service_runtime,
    )


class _FakePluginManager:
    def __init__(
        self,
        candidates: list[PluginCandidate] | None = None,
        manifests: list[PluginManifest] | None = None,
        **kwargs,
    ):
        self.kwargs = kwargs
        self._candidates = candidates or []
        self._manifests = manifests or []
        self.refresh_calls = 0
        self.find_calls = 0
        self._status = {"enabled": len(self._candidates), "cache_hits": 0, "re_embedded": 0}

    def refresh(self) -> dict:
        self.refresh_calls += 1
        self._status = {"enabled": len(self._candidates), "cache_hits": 1, "re_embedded": 0}
        return dict(self._status)

    def status(self) -> dict:
        return dict(self._status)

    def discovered_manifests(self) -> tuple[PluginManifest, ...]:
        return tuple(self._manifests)

    def find_candidates(self, prompt: str, top_n: int, min_score: float | None = None) -> list[PluginCandidate]:
        self.find_calls += 1
        candidates = list(self._candidates)[:top_n]
        if min_score is None:
            return candidates
        return [candidate for candidate in candidates if candidate.score >= min_score]


class _FakePluginServiceManager:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.registered_manifests: list[PluginManifest] = []
        self.start_auto_calls = 0
        self.stop_all_calls = 0
        self._service_ids: tuple[str, ...] = ()

    def register_manifests(self, manifests: list[PluginManifest]) -> dict:
        self.registered_manifests = list(manifests)
        self._service_ids = tuple(
            manifest.plugin_id
            for manifest in manifests
            if manifest.enabled and manifest.runtime_mode in {"service", "hybrid"}
        )
        return self.status()

    def start_auto_services(self) -> None:
        self.start_auto_calls += 1

    def stop_all(self) -> None:
        self.stop_all_calls += 1

    def service_ids(self) -> tuple[str, ...]:
        return self._service_ids

    def status(self) -> dict:
        return {
            "registered": len(self._service_ids),
            "dependency_invalid": 0,
            "services": {plugin_id: {"state": "discovered"} for plugin_id in self._service_ids},
        }


class _FakeEmbeddingProvider:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.model_id = kwargs.get("model_id", "fake-embedding")


class _FakePluginRouter:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeConfigManager:
    def config_value(self, section: str, key: str, default=None):
        return default

    def int_config_value(self, section: str, key: str, default=None):
        return default


class OracPluginIntegrationTests(unittest.TestCase):
    """Tests the integration seam between Orac request handling and plugin routing."""

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

    def _make_orac_stub(self) -> Orac:
        orchestrator = Orac.__new__(Orac)
        orchestrator._plugin_routing_enabled = True
        orchestrator._plugin_routing_ready = False
        orchestrator._plugin_routing_candidate_count = 3
        orchestrator._plugin_routing_min_score = None
        orchestrator.plugin_manager = None
        orchestrator.plugin_router = None
        orchestrator.plugin_service_manager = None
        orchestrator.config_mgr = object()
        orchestrator.ctx = object()
        return orchestrator

    def setUp(self) -> None:
        self._original_logger = orac_module.logger
        orac_module.logger = self._FakeLogger()

    def tearDown(self) -> None:
        orac_module.logger = self._original_logger

    def test_ensure_plugin_routing_ready_skips_refresh_when_already_ready(self) -> None:
        orchestrator = self._make_orac_stub()
        orchestrator._plugin_routing_ready = True
        orchestrator.plugin_manager = _FakePluginManager()

        report = orchestrator._ensure_plugin_routing_ready()

        self.assertEqual(report, orchestrator.plugin_manager.status())
        self.assertEqual(orchestrator.plugin_manager.refresh_calls, 0)

    def test_collect_plugin_routing_handoff_refreshes_when_requested(self) -> None:
        orchestrator = self._make_orac_stub()
        orchestrator.plugin_manager = _FakePluginManager(
            candidates=[PluginCandidate(plugin_id="home_assistant", score=0.9)]
        )

        handoff = orchestrator._collect_plugin_routing_handoff(
            "Turn on the kitchen lights.",
            {"plugin_routing_refresh": True},
        )

        self.assertIsNotNone(handoff)
        self.assertTrue(handoff.refreshed)
        self.assertEqual(orchestrator.plugin_manager.refresh_calls, 1)
        self.assertEqual(orchestrator.plugin_manager.find_calls, 1)

    def test_collect_plugin_routing_handoff_returns_none_when_no_candidates(self) -> None:
        orchestrator = self._make_orac_stub()
        orchestrator.plugin_manager = _FakePluginManager(candidates=[])

        handoff = orchestrator._collect_plugin_routing_handoff("Hello there", {})

        self.assertIsNone(handoff)
        joined = "\n".join(message for _, message in orac_module.logger.messages)
        self.assertIn("found no candidate plugins", joined)
        self.assertIn(("debug", "Plugin routing found no candidate plugins; using normal conversational flow."), orac_module.logger.messages)

    def test_init_plugin_routing_creates_plugin_service_manager(self) -> None:
        orchestrator = self._make_orac_stub()
        orchestrator.config_mgr = _FakeConfigManager()
        orchestrator._plugin_routing_bootstrap_on_startup = False

        with (
            patch.object(orac_module, "HashEmbeddingProvider", _FakeEmbeddingProvider),
            patch.object(orac_module, "PluginManager", _FakePluginManager),
            patch.object(orac_module, "PluginRouter", _FakePluginRouter),
            patch.object(orac_module, "PluginServiceManager", _FakePluginServiceManager),
        ):
            orchestrator._init_plugin_routing()

        self.assertIsInstance(orchestrator.plugin_service_manager, _FakePluginServiceManager)
        self.assertIsInstance(orchestrator.plugin_router, _FakePluginRouter)

    def test_refresh_registers_discovered_service_and_hybrid_manifests(self) -> None:
        manifests = [
            _manifest("svc_auto", runtime_mode="service", start_policy="auto"),
            _manifest("hybrid_manual", runtime_mode="hybrid", start_policy="manual"),
            _manifest("normal", runtime_mode="on_demand"),
        ]
        orchestrator = self._make_orac_stub()
        orchestrator.plugin_manager = _FakePluginManager(manifests=manifests)
        service_manager = _FakePluginServiceManager()
        orchestrator.plugin_service_manager = service_manager

        report = orchestrator.refresh_plugin_routing()

        self.assertIsNotNone(report)
        self.assertEqual(orchestrator.plugin_manager.refresh_calls, 1)
        self.assertEqual(
            [manifest.plugin_id for manifest in service_manager.registered_manifests],
            ["svc_auto", "hybrid_manual"],
        )
        self.assertEqual(service_manager.start_auto_calls, 1)
        self.assertEqual(report["service_lifecycle"]["registered"], 2)

    def test_refresh_stops_existing_services_before_reregistering(self) -> None:
        orchestrator = self._make_orac_stub()
        orchestrator.plugin_manager = _FakePluginManager(
            manifests=[_manifest("svc_auto", runtime_mode="service", start_policy="auto")]
        )
        service_manager = _FakePluginServiceManager()
        service_manager._service_ids = ("svc_old",)
        orchestrator.plugin_service_manager = service_manager

        orchestrator.refresh_plugin_routing()

        self.assertEqual(service_manager.stop_all_calls, 1)

    def test_shutdown_stops_managed_plugin_services(self) -> None:
        orchestrator = self._make_orac_stub()
        service_manager = _FakePluginServiceManager()
        orchestrator.plugin_service_manager = service_manager

        orchestrator.shutdown()

        self.assertEqual(service_manager.stop_all_calls, 1)

    def test_render_plugin_routing_hints_is_narrow_and_scored(self) -> None:
        handoff = PluginRoutingHandoff(
            candidates=(
                PluginCandidate(plugin_id="home_assistant", score=0.9231),
                PluginCandidate(plugin_id="media_control", score=0.8123),
            ),
            refreshed=False,
        )

        block = render_plugin_routing_hints(handoff)

        self.assertIn("PLUGIN ROUTING CANDIDATES", block)
        self.assertIn("plugin_id: home_assistant; score: 0.9231", block)
        self.assertIn("plugin_id: media_control; score: 0.8123", block)
        self.assertNotIn("description", block)
        self.assertNotIn("capabilities", block)


if __name__ == "__main__":
    unittest.main()
