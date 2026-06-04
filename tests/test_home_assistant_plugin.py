"""Tests for the Home Assistant on-demand command plugin."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Verifies narrow Home Assistant resync command routing.

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for path in (SRC_ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from home_assistant.plugin import HomeAssistantPlugin
from model.plugin_router import PluginRouter
import model.plugin_router as plugin_router_module
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_routing.models import PluginCandidate


class _FakeLogger:
    def __init__(self) -> None:
        self.info: list[str] = []
        self.error: list[str] = []
        self.debug: list[str] = []
        self.warning: list[str] = []

    def log_info(self, message: str) -> None:
        self.info.append(message)

    def log_error(self, message: str) -> None:
        self.error.append(message)

    def log_debug(self, message: str) -> None:
        self.debug.append(message)

    def log_warning(self, message: str) -> None:
        self.warning.append(message)


class _FakeConfigManager:
    def config_value(self, section: str, key: str, default=None):
        return default


class _FakeRuntimeContext:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.commands: list[dict] = []

    def run_service_command(
        self,
        plugin_id: str,
        command: str,
        payload: dict | None = None,
    ) -> dict:
        self.commands.append(
            {
                "plugin_id": plugin_id,
                "command": command,
                "payload": payload or {},
            }
        )
        if self.fail:
            raise RuntimeError("sync failed")
        return {"status": "complete"}


class _FakePluginManager:
    def __init__(self, manifest) -> None:
        self._manifest = manifest

    def get_manifest(self, plugin_id: str):
        if plugin_id == self._manifest.plugin_id:
            return self._manifest
        return None


class _FakeContextManager:
    pass


class _FakeServiceManager:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.commands: list[dict] = []

    def run_service_command(
        self,
        plugin_id: str,
        command: str,
        payload: dict | None = None,
    ) -> dict:
        self.commands.append(
            {
                "plugin_id": plugin_id,
                "command": command,
                "payload": payload or {},
            }
        )
        if self.fail:
            raise RuntimeError("sync failed")
        return {"status": "complete"}


def _home_assistant_manifest():
    manifests, errors = PluginDiscovery(Path("plugins")).discover()
    if errors:
        raise AssertionError(errors)
    return next(
        manifest for manifest in manifests if manifest.plugin_id == "home_assistant"
    )


class HomeAssistantPluginTests(unittest.TestCase):
    """Tests Home Assistant command plugin behaviour."""

    def test_recognised_resync_phrases_are_handled(self) -> None:
        plugin = HomeAssistantPlugin(runtime_context=_FakeRuntimeContext())

        for phrase in (
            "Resync devices",
            "Sync devices",
            "Resync Home Assistant",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(plugin.can_handle(phrase))

    def test_unrelated_phrases_are_not_matched(self) -> None:
        plugin = HomeAssistantPlugin(runtime_context=_FakeRuntimeContext())

        for phrase in (
            "sync",
            "sync music",
            "turn on the kitchen lights",
            "resync calendar",
        ):
            with self.subTest(phrase=phrase):
                self.assertFalse(plugin.can_handle(phrase))
                self.assertIsNone(plugin.execute(phrase))

    def test_successful_command_calls_managed_service_path(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("Resync devices")

        self.assertIsNotNone(result)
        self.assertEqual(result.plugin_id, "home_assistant")
        self.assertIn("Resyncing Home Assistant devices and entities.", result.content)
        self.assertIn("Home Assistant sync complete.", result.content)
        self.assertEqual(
            runtime_context.commands,
            [
                {
                    "plugin_id": "home_assistant",
                    "command": "resync",
                    "payload": {"source": "voice_command"},
                }
            ],
        )

    def test_failed_command_returns_failure_response_and_logs(self) -> None:
        logger = _FakeLogger()
        plugin = HomeAssistantPlugin(
            logger=logger,
            runtime_context=_FakeRuntimeContext(fail=True),
        )

        result = plugin.execute("Resync Home Assistant")

        self.assertIsNotNone(result)
        self.assertIn("Home Assistant sync failed.", result.content)
        self.assertTrue(any("sync failed" in message for message in logger.error))

    def test_router_dispatches_recognised_phrases_to_home_assistant_plugin(self) -> None:
        manifest = _home_assistant_manifest()

        for phrase in (
            "Resync devices",
            "Sync devices",
            "Resync Home Assistant",
        ):
            with self.subTest(phrase=phrase):
                service_manager = _FakeServiceManager()
                router = PluginRouter(
                    plugin_manager=_FakePluginManager(manifest),
                    logger=_FakeLogger(),
                    config_mgr=_FakeConfigManager(),
                    context_manager=_FakeContextManager(),
                    plugin_service_manager=service_manager,
                    plugin_db_session_factory=lambda: object(),
                )
                handoff = PluginRoutingHandoff(
                    candidates=(PluginCandidate(plugin_id="home_assistant", score=0.99),),
                    refreshed=False,
                )

                with patch.object(
                    plugin_router_module,
                    "load_plugin_class",
                    return_value=HomeAssistantPlugin,
                ):
                    result = router.route(
                        phrase,
                        {},
                        handoff,
                        "unit_user",
                    )

                self.assertIsNotNone(result)
                self.assertEqual(result.plugin_id, "home_assistant")
                self.assertEqual(
                    service_manager.commands[0]["command"],
                    "resync",
                )


if __name__ == "__main__":
    unittest.main()
