"""Tests for the minimal plugin runtime loader."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Verifies the entry-point loader used by the first functioning Orac plugin.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_config import PluginConfigManager
from model.plugin_runtime import load_plugin_class, load_plugin_service_class
from model.plugin_runtime import PluginRuntimeContext


class PluginRuntimeTests(unittest.TestCase):
    """Tests the modest plugin execution loader."""

    def test_weather_plugin_entry_point_loads(self) -> None:
        manifests, errors = PluginDiscovery(Path("plugins")).discover()
        self.assertEqual(errors, [])
        weather_manifest = next(manifest for manifest in manifests if manifest.plugin_id == "weather")

        plugin_class = load_plugin_class(weather_manifest)

        self.assertEqual(plugin_class.__name__, "WeatherPlugin")
        self.assertEqual(weather_manifest.execution_policy.action_type, "informational_read_only")
        self.assertTrue(weather_manifest.execution_policy.allowed_by_default)
        self.assertFalse(weather_manifest.execution_policy.requires_confirmation)

    def test_home_assistant_service_entry_point_loads(self) -> None:
        manifests, errors = PluginDiscovery(Path("plugins")).discover()
        self.assertEqual(errors, [])
        manifest = next(
            manifest for manifest in manifests if manifest.plugin_id == "home_assistant"
        )

        plugin_class = load_plugin_service_class(manifest)

        self.assertEqual(plugin_class.__name__, "HomeAssistantService")
        self.assertEqual(manifest.execution_policy.action_type, "local_mutation")
        self.assertFalse(manifest.execution_policy.requires_confirmation)
        self.assertTrue(manifest.execution_policy.allowed_by_default)
        self.assertFalse(manifest.execution_policy.scaffold)
        self.assertIn("home_assistant.resync", manifest.capabilities)
        self.assertIsNotNone(manifest.secrets)
        self.assertEqual(manifest.secrets.default_key, "access_token")
        self.assertFalse(manifest.secrets.allow_custom_keys)
        self.assertEqual(manifest.secrets.key_names(), ("access_token",))
        self.assertTrue(manifest.secrets.get_key("access_token").required)

    def test_runtime_context_exposes_current_plugin_config_only(self) -> None:
        manifests, errors = PluginDiscovery(Path("plugins")).discover()
        self.assertEqual(errors, [])
        manifest = next(
            manifest for manifest in manifests if manifest.plugin_id == "home_assistant"
        )
        config_manager = PluginConfigManager(manifest)
        context = PluginRuntimeContext(
            manifest=manifest,
            logger=None,
            config_mgr=None,
            auth_user="clive",
            plugin_config_manager=config_manager,
        )

        self.assertIs(context.plugin_config(), config_manager)
        self.assertEqual(context.plugin_config().plugin_id, "home_assistant")
        self.assertFalse(hasattr(context.plugin_config(), "for_plugin"))


if __name__ == "__main__":
    unittest.main()
