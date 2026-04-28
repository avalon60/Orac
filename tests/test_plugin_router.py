"""Tests for plugin execution orchestration."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Verifies that plugin routing candidates are executed outside the controller.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_router import PluginRouter
import model.plugin_router as plugin_router_module
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_routing.models import PluginCandidate, PluginManifest
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
    def __init__(self, manifest: PluginManifest | None):
        self._manifest = manifest

    def get_manifest(self, plugin_id: str) -> PluginManifest | None:
        if self._manifest and self._manifest.plugin_id == plugin_id:
            return self._manifest
        return None


class PluginRouterTests(unittest.TestCase):
    """Tests the dedicated plugin execution orchestrator."""

    def test_router_returns_first_handled_result(self) -> None:
        logger = _FakeLogger()
        manifest = PluginManifest(
            schema_version=1,
            plugin_id="weather",
            name="Weather",
            description="Weather plugin",
            version="1.0.0",
            enabled=True,
            capabilities=("weather.current_conditions",),
            entities=(),
            examples=(),
            entry_point="plugin:WeatherPlugin",
            manifest_path=Path("plugins/weather.json"),
            plugin_dir=Path("plugins/weather"),
            manifest_hash="abc123",
        )
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=logger,
            config_mgr=object(),
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
            )
        finally:
            plugin_router_module.load_plugin_class = original_loader

        self.assertIsNotNone(result)
        self.assertEqual(result.plugin_id, "weather")
        self.assertEqual(result.content, "Direct weather answer")

    def test_router_falls_back_when_no_plugin_handles(self) -> None:
        logger = _FakeLogger()
        router = PluginRouter(
            plugin_manager=_FakePluginManager(None),
            logger=logger,
            config_mgr=object(),
        )

        result = router.route(
            "Hello there",
            {},
            PluginRoutingHandoff(
                candidates=(PluginCandidate(plugin_id="weather", score=0.80),),
                refreshed=False,
            ),
        )

        self.assertIsNone(result)
        self.assertIn(
            ("debug", "No plugin candidate handled the request directly; falling back to conversational flow."),
            logger.messages,
        )


if __name__ == "__main__":
    unittest.main()
