"""Tests the Orac integration seam for plugin routing candidate retrieval."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Verifies startup/bootstrap guards and request-flow handoff formatting for plugin routing.

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest

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
from model.plugin_routing.models import PluginCandidate


class _FakePluginManager:
    def __init__(self, candidates: list[PluginCandidate] | None = None):
        self._candidates = candidates or []
        self.refresh_calls = 0
        self.find_calls = 0
        self._status = {"enabled": len(self._candidates), "cache_hits": 0, "re_embedded": 0}

    def refresh(self) -> dict:
        self.refresh_calls += 1
        self._status = {"enabled": len(self._candidates), "cache_hits": 1, "re_embedded": 0}
        return dict(self._status)

    def status(self) -> dict:
        return dict(self._status)

    def find_candidates(self, prompt: str, top_n: int, min_score: float | None = None) -> list[PluginCandidate]:
        self.find_calls += 1
        candidates = list(self._candidates)[:top_n]
        if min_score is None:
            return candidates
        return [candidate for candidate in candidates if candidate.score >= min_score]


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
        orchestrator.config_mgr = object()
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
