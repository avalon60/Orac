"""Tests for plugin-scoped configuration loading."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Verifies plugin-local plugin.ini validation and access.

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_config import PluginConfigError
from model.plugin_config import PluginConfigManager
from model.plugin_routing.discovery import PluginDiscovery


def _runtime() -> dict:
    return {"mode": "on_demand"}


def _manifest(plugin_id: str, *, required_config: bool = True) -> dict:
    configuration = {
        "required": (
            [
                {
                    "section": plugin_id,
                    "key": "host",
                    "type": "string",
                    "description": "Plugin host.",
                },
                {
                    "section": plugin_id,
                    "key": "port",
                    "type": "int",
                    "description": "Plugin port.",
                },
            ]
            if required_config
            else []
        ),
        "optional": [
            {
                "section": plugin_id,
                "key": "enabled",
                "type": "bool",
                "description": "Plugin enabled flag.",
            }
        ],
    }
    return {
        "schema_version": 2,
        "plugin_id": plugin_id,
        "name": plugin_id.title(),
        "description": "Test plugin.",
        "version": "1.0.0",
        "enabled": True,
        "capabilities": [f"{plugin_id}.query"],
        "entitlements": [],
        "entry_point": "plugin:TestPlugin",
        "runtime": _runtime(),
        "configuration": configuration,
    }


def _write_plugin(
    plugins_dir: Path,
    plugin_id: str,
    *,
    required_config: bool = True,
    plugin_ini: str | None = None,
) -> None:
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("class TestPlugin:\n    pass\n", encoding="utf-8")
    if plugin_ini is not None:
        (plugin_dir / "plugin.ini").write_text(plugin_ini, encoding="utf-8")
    (plugins_dir / f"{plugin_id}.json").write_text(
        json.dumps(_manifest(plugin_id, required_config=required_config)),
        encoding="utf-8",
    )


def _discover_one(plugins_dir: Path, plugin_id: str):
    manifests, errors = PluginDiscovery(plugins_dir).discover()
    if errors:
        raise AssertionError(errors)
    return next(manifest for manifest in manifests if manifest.plugin_id == plugin_id)


class PluginConfigManagerTests(unittest.TestCase):
    """Tests plugin-local configuration validation and scoped access."""

    def test_loads_plugin_local_ini_with_typed_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            _write_plugin(
                plugins_dir,
                "alpha",
                plugin_ini="[alpha]\nhost = alpha.local\nport = 8123\nenabled = true\n",
            )
            manager = PluginConfigManager(_discover_one(plugins_dir, "alpha"))

            result = manager.validate()

            self.assertTrue(result.eligible)
            self.assertEqual(result.status, "configured")
            self.assertEqual(manager.config_value("alpha", "host"), "alpha.local")
            self.assertEqual(manager.int_config_value("alpha", "port"), 8123)
            self.assertTrue(manager.bool_config_value("alpha", "enabled"))

    def test_plugin_ini_is_optional_when_no_required_config_is_declared(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            _write_plugin(plugins_dir, "alpha", required_config=False)
            manager = PluginConfigManager(_discover_one(plugins_dir, "alpha"))

            result = manager.validate()

            self.assertTrue(result.eligible)
            self.assertEqual(result.status, "not_required")

    def test_missing_required_plugin_ini_disables_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            _write_plugin(plugins_dir, "alpha")
            manager = PluginConfigManager(_discover_one(plugins_dir, "alpha"))

            result = manager.validate()

            self.assertFalse(result.eligible)
            self.assertEqual(result.status, "missing_required")
            self.assertIn("alpha.host", result.missing_keys)
            self.assertIn("plugin_init.sh alpha", result.message)

    def test_missing_required_key_disables_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            _write_plugin(
                plugins_dir,
                "alpha",
                plugin_ini="[alpha]\nhost = alpha.local\n",
            )
            manager = PluginConfigManager(_discover_one(plugins_dir, "alpha"))

            result = manager.validate()

            self.assertFalse(result.eligible)
            self.assertEqual(result.status, "missing_required")
            self.assertEqual(result.missing_keys, ("alpha.port",))

    def test_uninitialised_placeholder_disables_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            _write_plugin(
                plugins_dir,
                "alpha",
                plugin_ini="[alpha]\nhost = %host%\nport = 8123\n",
            )
            manager = PluginConfigManager(_discover_one(plugins_dir, "alpha"))

            result = manager.validate()

            self.assertFalse(result.eligible)
            self.assertEqual(result.status, "uninitialised")
            self.assertEqual(result.uninitialised_keys, ("alpha.host",))
            self.assertIn("plugin_init.sh alpha", result.message)

    def test_manager_is_scoped_to_one_plugin_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            _write_plugin(
                plugins_dir,
                "alpha",
                plugin_ini="[alpha]\nhost = alpha.local\nport = 8123\n",
            )
            _write_plugin(
                plugins_dir,
                "beta",
                plugin_ini="[beta]\nhost = beta.local\nport = 8124\n",
            )
            alpha_manager = PluginConfigManager(_discover_one(plugins_dir, "alpha"))

            self.assertEqual(alpha_manager.config_value("alpha", "host"), "alpha.local")
            with self.assertRaises(PluginConfigError):
                alpha_manager.config_value("beta", "host")


if __name__ == "__main__":
    unittest.main()
