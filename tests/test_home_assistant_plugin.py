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

from home_assistant.interceptor import HomeAssistantDialogInterceptor
from home_assistant.plugin import HomeAssistantPlugin
from model.plugin_resources import resource_reader_for_manifest
from model.plugin_router import PluginRouter
import model.plugin_router as plugin_router_module
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_routing.interception import route_candidate_from_intercept


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
        self.manifest = PluginDiscovery(PROJECT_ROOT / "plugins").load_manifest(
            PROJECT_ROOT / "plugins" / "home_assistant.json"
        )

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
        if command == "control":
            return {
                "status": "confirmed",
                "entity_ids": ["light.kitchen"],
            }
        if command == "list_area":
            return {
                "status": "complete",
                "area_name": "office",
                "requested_domain": None,
                "devices": [
                    {
                        "name": "desk lamp",
                        "entity_ids": ["switch.desk_lamp"],
                        "domains": ["switch"],
                    },
                    {
                        "name": "printer",
                        "entity_ids": ["switch.printer"],
                        "domains": ["switch"],
                    },
                ],
            }
        if command == "list_areas":
            return {
                "status": "complete",
                "areas": ["office", "kitchen"],
            }
        if command == "sensor_query":
            return {
                "status": "complete",
                "content": (
                    "The Lounge temperature is 21.4°C. That is comfortable. "
                    "It last updated 12 minutes ago."
                ),
                "entity_ids": ["sensor.lounge_temperature"],
                "areas": ["lounge"],
            }
        if command == "light_control":
            return {
                "status": "confirmed",
                "content": "TV light set to 50 percent.",
                "entity_ids": ["light.tv_light"],
            }
        if command == "light_state_query":
            return {
                "status": "complete",
                "content": "The TV light is on.",
                "entity_ids": ["light.tv_light"],
                "areas": [],
                "source": "live_home_assistant",
            }
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


def _home_assistant_route_candidate(prompt: str):
    """Return the core route candidate produced by the Home Assistant interceptor."""
    manifest = _home_assistant_manifest()
    interceptor = HomeAssistantDialogInterceptor(
        manifest=manifest,
        resources=resource_reader_for_manifest(manifest),
    )
    interceptor.prepare()
    match = interceptor.intercept(prompt)
    assert match is not None
    return route_candidate_from_intercept(match, manifest)


class HomeAssistantPluginTests(unittest.TestCase):
    """Tests Home Assistant command plugin behaviour."""

    def test_recognised_resync_phrases_are_handled(self) -> None:
        plugin = HomeAssistantPlugin(runtime_context=_FakeRuntimeContext())

        for phrase in (
            "Resync devices",
            "Sync devices",
            "Sync Home Assistant devices",
            "Resync Home Assistant",
            "Resync Home Assistant devices",
            "Synchronize devices",
            "Synchronize Home Assistant",
            "Synchronize Home Assistant devices",
            "Synchronise devices",
            "Synchronise Home Assistant",
            "Synchronise Home Assistant devices",
            "Sink devices",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(plugin.can_handle(phrase))

    def test_unrelated_phrases_are_not_matched(self) -> None:
        plugin = HomeAssistantPlugin(runtime_context=_FakeRuntimeContext())

        for phrase in (
            "sync",
            "sink",
            "sync music",
            "sink music",
            "resync calendar",
            "synchronize calendar",
            "synchronise calendar",
        ):
            with self.subTest(phrase=phrase):
                self.assertFalse(plugin.can_handle(phrase))
                self.assertIsNone(plugin.execute(phrase))

    def test_area_inventory_dispatches_structured_service_command(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("List areas")

        self.assertIn("Home Assistant areas", result.content)
        self.assertEqual(runtime_context.commands[0]["command"], "list_areas")

    def test_device_control_dispatches_structured_service_command(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("Turn on the kitchen lights")

        self.assertIn("Home Assistant confirmed", result.content)
        self.assertEqual(runtime_context.commands[0]["command"], "control")
        self.assertEqual(
            runtime_context.commands[0]["payload"],
            {
                "action": "turn_on",
                "target": "kitchen lights",
                "requested_domain": "light",
            },
        )

    def test_voice_punctuation_and_dropped_switch_verb_are_handled(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("Off the desk lamp.")

        self.assertIn("Home Assistant confirmed", result.content)
        self.assertEqual(
            runtime_context.commands[0]["payload"],
            {
                "action": "turn_off",
                "target": "desk lamp",
                "requested_domain": "light",
            },
        )

    def test_terse_target_control_dispatches_structured_service_command(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("Desk lamp off")

        self.assertIn("Home Assistant confirmed", result.content)
        self.assertEqual(
            runtime_context.commands[0]["payload"],
            {
                "action": "turn_off",
                "target": "desk lamp",
                "requested_domain": "light",
            },
        )

    def test_terse_target_control_does_not_claim_unverified_success(self) -> None:
        class _UnconfirmedRuntimeContext(_FakeRuntimeContext):
            def run_service_command(
                self,
                plugin_id: str,
                command: str,
                payload: dict | None = None,
            ) -> dict:
                result = super().run_service_command(plugin_id, command, payload)
                if command == "control":
                    return {
                        "status": "accepted_unverified",
                        "entity_ids": ["light.tv_light"],
                    }
                return result

        runtime_context = _UnconfirmedRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("TV light on.")

        self.assertEqual(runtime_context.commands[0]["command"], "control")
        self.assertIn("control was not confirmed", result.content.lower())
        self.assertNotIn("confirmed turn on", result.content.lower())

    def test_area_listing_dispatches_read_only_service_command(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("What devices are in the office?")

        self.assertEqual(
            runtime_context.commands[0],
            {
                "plugin_id": "home_assistant",
                "command": "list_area",
                "payload": {"area": "office", "requested_domain": None},
            },
        )
        self.assertEqual(
            result.content,
            "Home Assistant devices in Office: Desk Lamp, Printer.",
        )
        self.assertEqual(result.provenance["command"], "home_assistant.area_list")

    def test_area_first_listing_dispatches_the_exact_area_name(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        plugin.execute("List living room devices")

        self.assertEqual(
            runtime_context.commands[0],
            {
                "plugin_id": "home_assistant",
                "command": "list_area",
                "payload": {
                    "area": "living room",
                    "requested_domain": None,
                },
            },
        )

    def test_light_control_dispatches_structured_service_command(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("Set the TV light to 50 percent")

        self.assertEqual(
            runtime_context.commands[0],
            {
                "plugin_id": "home_assistant",
                "command": "light_control",
                "payload": {
                    "target": "tv light",
                    "kind": "brightness_pct",
                    "value": 50,
                    "label": None,
                    "turn_on": True,
                },
            },
        )
        self.assertIn("TV light set to 50 percent.", result.content)
        self.assertEqual(result.provenance["command"], "home_assistant.light_control")

    def test_light_state_query_dispatches_structured_service_command(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("Is the TV light on?")

        self.assertEqual(
            runtime_context.commands[0],
            {
                "plugin_id": "home_assistant",
                "command": "light_state_query",
                "payload": {
                    "intent": "state",
                    "target": "tv light",
                    "scope": "entity",
                    "requested_domain": "light",
                    "requested_label": None,
                },
            },
        )
        self.assertIn("TV light is on.", result.content)
        self.assertEqual(result.provenance["command"], "home_assistant.light_state_query")

    def test_filtered_area_listing_uses_correct_plural(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("List switches in the office")

        self.assertIn("Home Assistant switches in Office", result.content)

    def test_sensor_query_dispatches_read_only_structured_service_command(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("What's the temperature in the lounge?")

        self.assertIn("Lounge temperature is 21.4°C", result.content)
        self.assertEqual(
            runtime_context.commands[0],
            {
                "plugin_id": "home_assistant",
                "command": "sensor_query",
                "payload": {
                    "intent": "area_temperature",
                    "areas": ["lounge"],
                    "sensor_role": "temperature",
                },
            },
        )
        self.assertEqual(
            result.provenance["command"],
            "home_assistant.sensor_query",
        )

    def test_whole_home_control_is_refused_without_service_dispatch(self) -> None:
        runtime_context = _FakeRuntimeContext()
        plugin = HomeAssistantPlugin(runtime_context=runtime_context)

        result = plugin.execute("Turn off all lights")

        self.assertIn("not performed", result.content)
        self.assertEqual(result.provenance["failure_type"], "whole_home_refused")
        self.assertEqual(runtime_context.commands, [])

    def test_successful_command_calls_managed_service_path(self) -> None:
        for phrase in (
            "Resync devices",
            "Sync devices",
            "Sync Home Assistant devices",
            "Resync Home Assistant",
            "Resync Home Assistant devices",
            "Synchronize devices",
            "Synchronize Home Assistant",
            "Synchronize Home Assistant devices",
            "Synchronise devices",
            "Synchronise Home Assistant",
            "Synchronise Home Assistant devices",
            "Sink devices",
        ):
            with self.subTest(phrase=phrase):
                runtime_context = _FakeRuntimeContext()
                plugin = HomeAssistantPlugin(runtime_context=runtime_context)

                result = plugin.execute(phrase)

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

        cases = {
            "Resync devices": "resync",
            "Sync devices": "resync",
            "Sync Home Assistant devices": "resync",
            "Resync Home Assistant": "resync",
            "Resync Home Assistant devices": "resync",
            "Synchronize Home Assistant Devices": "resync",
            "Synchronise Home Assistant Devices": "resync",
            "Sink devices": "resync",
            "Desk lamp off": "control",
            "Set the TV light to 50 percent": "light_control",
            "Is the TV light on?": "light_state_query",
            "How bright is the TV light?": "light_state_query",
            "List devices in the office": "list_area",
            "List living room devices": "list_area",
            "What lights are in the kitchen?": "list_area",
            "What's the temperature in the lounge?": "sensor_query",
            "Are any sensors unavailable?": "sensor_query",
        }
        for phrase, expected_command in cases.items():
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
                    candidates=(_home_assistant_route_candidate(phrase),),
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
                    expected_command,
                )


if __name__ == "__main__":
    unittest.main()
