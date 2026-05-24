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
from model.plugin_runtime import load_plugin_class, load_plugin_service_class


class PluginRuntimeTests(unittest.TestCase):
    """Tests the modest plugin execution loader."""

    def test_weather_plugin_entry_point_loads(self) -> None:
        manifests, errors = PluginDiscovery(Path("plugins")).discover()
        self.assertEqual(errors, [])
        weather_manifest = next(manifest for manifest in manifests if manifest.plugin_id == "weather")

        plugin_class = load_plugin_class(weather_manifest)

        self.assertEqual(plugin_class.__name__, "WeatherPlugin")

    def test_home_assistant_service_entry_point_loads(self) -> None:
        manifests, errors = PluginDiscovery(Path("plugins")).discover()
        self.assertEqual(errors, [])
        manifest = next(
            manifest for manifest in manifests if manifest.plugin_id == "home_assistant"
        )

        plugin_class = load_plugin_service_class(manifest)

        self.assertEqual(plugin_class.__name__, "HomeAssistantService")


if __name__ == "__main__":
    unittest.main()
