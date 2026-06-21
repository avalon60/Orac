"""Unit tests for the plugin routing subsystem."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Verifies manifest validation, cache invalidation, and candidate search behaviour.

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_database_deployment import PluginDatabaseDeploymentResult
from model.plugin_routing.embeddings import HashEmbeddingProvider
from model.plugin_routing.index import PluginIntentIndex
from model.plugin_routing.intent_text import INTENT_TEXT_VERSION, build_canonical_intent_text
from model.plugin_routing.manager import PluginManager
from model.plugin_registry import PluginRegistryError


class _SuccessfulDatabaseDeployer:
    def deploy_if_needed(self, manifest):
        status = "deployed" if manifest.database_required else "not_required"
        return PluginDatabaseDeploymentResult(
            plugin_id=manifest.plugin_id,
            status=status,
            eligible=True,
            message="test deployment allowed",
        )


class _CountingDatabaseDeployer(_SuccessfulDatabaseDeployer):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def deploy_if_needed(self, manifest):
        self.calls.append(manifest.plugin_id)
        return super().deploy_if_needed(manifest)


class _ManifestRegistry:
    def __init__(self, manifests):
        self.manifests = list(manifests)

    def enabled_manifests(self):
        return list(self.manifests)


class _FailingRegistry:
    def enabled_manifests(self):
        raise PluginRegistryError("registry unavailable")


class PluginRoutingTests(unittest.TestCase):
    """Tests the first working version of the plugin routing scaffold."""

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

    def test_registry_gated_refresh_does_not_redeploy_database_payloads(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp_plugins_dir,
            tempfile.TemporaryDirectory() as temp_cache_dir,
        ):
            plugins_dir = Path(temp_plugins_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )
            manifests, errors = PluginDiscovery(plugins_dir).discover()
            self.assertEqual(errors, [])
            deployer = _CountingDatabaseDeployer()
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
                database_deployer=deployer,
                registry_store=_ManifestRegistry(manifests),
                require_registry=True,
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertEqual(deployer.calls, [])

    def test_registry_failure_disables_plugins_without_breaking_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = self._FakeLogger()
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=Path(temp_dir) / "plugins",
                cache_dir=Path(temp_dir) / "cache",
                registry_store=_FailingRegistry(),
                require_registry=True,
                logger=logger,
            )

            report = manager.refresh()

            self.assertEqual(report["indexed_plugin_count"], 0)
            self.assertEqual(report["invalid"], 1)
            self.assertTrue(
                any("plugin routing is disabled" in message for _, message in logger.messages)
            )

    def test_discovery_rejects_mismatched_plugin_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "beta",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["test.capability"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("must exactly match manifest filename stem", errors[0])

    def test_discovery_accepts_manifest_without_ui_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.query"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(errors, [])
            self.assertIsNone(manifests[0].ui)

    def test_home_assistant_manifest_declares_valid_ui_surfaces(self) -> None:
        manifest = PluginDiscovery(PROJECT_ROOT / "plugins").load_manifest(
            PROJECT_ROOT / "plugins" / "home_assistant.json"
        )

        self.assertIsNotNone(manifest.ui)
        assert manifest.ui is not None
        self.assertEqual(
            manifest.ui.status_provider.provider_id,
            "home_assistant.status_summary",
        )
        self.assertTrue(manifest.ui.status_provider.redaction_required)
        self.assertEqual(
            [surface.surface_id for surface in manifest.ui.surfaces],
            [
                "home_assistant.admin_status",
                "home_assistant.react_diagnostics",
            ],
        )
        self.assertEqual(manifest.ui.surfaces[0].apex.app_alias, "ORAC_HA_STATUS")
        self.assertEqual(
            manifest.ui.surfaces[0].apex.app_export,
            "apex/f_home_assistant.sql",
        )
        self.assertFalse(manifest.ui.surfaces[0].apex.install_required)
        self.assertEqual(
            manifest.ui.surfaces[1].react.component,
            "HomeAssistantDiagnosticsPanel",
        )

    def test_home_assistant_manifest_declares_plugin_apex_app(self) -> None:
        manifest = PluginDiscovery(PROJECT_ROOT / "plugins").load_manifest(
            PROJECT_ROOT / "plugins" / "home_assistant.json"
        )

        self.assertEqual(len(manifest.apex_apps), 1)
        app = manifest.apex_apps[0]
        self.assertEqual(app.alias, "ORAC_HA_STATUS")
        self.assertEqual(app.label, "Home Assistant Status")
        self.assertEqual(app.app_export, "apex/f_home_assistant.sql")
        self.assertEqual(app.workspace, "ORAC")
        self.assertEqual(app.parsing_schema, "ORAC_APX_PUB")
        self.assertEqual(app.application_id, 10010)
        self.assertEqual(app.entry_page_id, 1)
        self.assertTrue(app.install_required)
        self.assertFalse(app.replace_existing)
        self.assertEqual(app.required_roles, ("ORAC_ADMIN",))
        self.assertTrue(app.enabled)

    def test_ui_surface_metadata_is_not_routing_metadata(self) -> None:
        manifest = PluginDiscovery(PROJECT_ROOT / "plugins").load_manifest(
            PROJECT_ROOT / "plugins" / "home_assistant.json"
        )

        route_values = {
            value
            for capability in manifest.route_capabilities
            for value in (
                capability.capability_id,
                *(intent.name for intent in capability.intents),
            )
        }

        self.assertNotIn("home_assistant.status_summary", route_values)
        self.assertNotIn("home_assistant.admin_status", route_values)
        self.assertNotIn("home_assistant.react_diagnostics", route_values)

    def test_ui_status_provider_redaction_required_defaults_true(self) -> None:
        manifest = self._load_temp_manifest(
            {
                "ui": {
                    "status_provider": {
                        "id": "alpha.status",
                        "format": "plugin_status_v1",
                    }
                }
            }
        )

        self.assertTrue(manifest.ui.status_provider.redaction_required)

    def test_discovery_rejects_invalid_ui_surface_values(self) -> None:
        cases = (
            ("target", "terminal"),
            ("type", "launcher"),
            ("audience", "anonymous"),
        )
        for field_name, invalid_value in cases:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, f"ui.surfaces\\[0\\].{field_name}"):
                    self._load_temp_manifest(
                        {
                            "ui": {
                                "surfaces": [
                                    {
                                        "id": "alpha.surface",
                                        "type": (
                                            invalid_value
                                            if field_name == "type"
                                            else "admin_status"
                                        ),
                                        "label": "Alpha Status",
                                        "target": (
                                            invalid_value
                                            if field_name == "target"
                                            else "apex"
                                        ),
                                        "audience": (
                                            invalid_value
                                            if field_name == "audience"
                                            else "admin"
                                        ),
                                        "enabled": True,
                                    }
                                ]
                            }
                        }
                    )

    def test_ui_apex_and_react_metadata_are_accepted(self) -> None:
        manifest = self._load_temp_manifest(
            {
                "ui": {
                    "surfaces": [
                        {
                            "id": "alpha.apex_status",
                            "type": "admin_status",
                            "label": "Alpha APEX",
                            "target": "apex",
                            "audience": "admin",
                            "enabled": True,
                            "apex": {
                                "app_alias": "ALPHA_STATUS",
                                "app_export": "apex/alpha_status.sql",
                                "entry_page_id": 1,
                                "install_required": False,
                            },
                        },
                        {
                            "id": "alpha.react_status",
                            "type": "diagnostic_panel",
                            "label": "Alpha React",
                            "target": "react",
                            "audience": "admin",
                            "enabled": True,
                            "react": {
                                "component": "AlphaStatusPanel",
                                "status_endpoint": "alpha.status",
                                "install_required": False,
                            },
                        },
                    ]
                }
            }
        )

        self.assertEqual(manifest.ui.surfaces[0].apex.entry_page_id, 1)
        self.assertEqual(manifest.ui.surfaces[1].react.status_endpoint, "alpha.status")

    def test_apex_apps_metadata_is_accepted_with_defensive_defaults(self) -> None:
        manifest = self._load_temp_manifest(
            {
                "apex_apps": [
                    {
                        "app_alias": "alpha_status",
                        "label": "Alpha Status",
                        "app_export": "apex/alpha_status.sql",
                        "install_required": True,
                    }
                ]
            }
        )

        self.assertEqual(len(manifest.apex_apps), 1)
        app = manifest.apex_apps[0]
        self.assertEqual(app.alias, "ALPHA_STATUS")
        self.assertEqual(app.workspace, "ORAC")
        self.assertEqual(app.parsing_schema, "ORAC_APX_PUB")
        self.assertEqual(app.entry_page_id, 1)
        self.assertFalse(app.replace_existing)
        self.assertTrue(app.enabled)

    def test_discovery_rejects_invalid_apex_app_values(self) -> None:
        cases = (
            ("workspace", "OTHER"),
            ("parsing_schema", "bad-schema"),
            ("app_export", "../escape.sql"),
            ("app_alias", "bad alias"),
        )
        for field_name, invalid_value in cases:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(ValueError, f"apex_apps\\[0\\].{field_name}"):
                    payload = {
                        "app_alias": "ALPHA_STATUS",
                        "label": "Alpha Status",
                        "app_export": "apex/alpha_status.sql",
                        "install_required": True,
                    }
                    payload[field_name] = invalid_value
                    self._load_temp_manifest({"apex_apps": [payload]})

    def test_apex_apps_are_not_routing_metadata(self) -> None:
        manifest = self._load_temp_manifest(
            {
                "apex_apps": [
                    {
                        "app_alias": "ALPHA_STATUS",
                        "label": "Alpha Status",
                        "app_export": "apex/alpha_status.sql",
                        "install_required": True,
                    }
                ]
            }
        )

        intent_text = build_canonical_intent_text(manifest)
        self.assertNotIn("ALPHA_STATUS", intent_text)
        self.assertNotIn("Alpha Status", intent_text)
        self.assertNotIn("alpha_status.sql", intent_text)

    def _load_temp_manifest(self, extra: dict) -> object:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            manifest_data = {
                "schema_version": 2,
                "plugin_id": "alpha",
                "name": "Alpha",
                "description": "Test plugin",
                "version": "1.0.0",
                "enabled": True,
                "capabilities": ["alpha.query"],
                "entitlements": [],
                "runtime": {"mode": "on_demand"},
            }
            manifest_data.update(extra)
            manifest_path = plugins_dir / "alpha.json"
            manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
            return PluginDiscovery(plugins_dir).load_manifest(manifest_path)

    def test_canonical_intent_text_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            manifest_path = plugins_dir / "alpha.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha Plugin",
                        "description": "Routes alpha tasks.",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control", "alpha.query"],
                        "entitlements": [],
                        "examples": ["Do the alpha thing."],
                        "entry_point": "plugin:AlphaPlugin",
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()
            self.assertEqual(errors, [])
            text = build_canonical_intent_text(manifests[0])

            expected = (
                "plugin_id: alpha\n"
                "name: Alpha Plugin\n"
                "description: Routes alpha tasks.\n"
                "capabilities:\n"
                "- alpha.control\n"
                "- alpha.query\n"
                "examples:\n"
                "- Do the alpha thing.\n"
            )
            self.assertEqual(text, expected)
            self.assertNotIn("version:", text)
            self.assertNotIn("entry_point:", text)
            self.assertNotIn("runtime:", text)
            self.assertNotIn("execution:", text)
            self.assertNotIn("configuration:", text)
            self.assertNotIn("database:", text)

    def test_discovery_loads_explicit_execution_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.query"],
                        "entitlements": ["users.username"],
                        "entry_point": "plugin:AlphaPlugin",
                        "execution": {
                            "action_type": "informational_read_only",
                            "requires_confirmation": False,
                            "allowed_by_default": True,
                            "capabilities": ["alpha.query"],
                            "entitlements": ["users.username"],
                        },
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(errors, [])
            self.assertEqual(manifests[0].execution_policy.action_type, "informational_read_only")
            self.assertEqual(manifests[0].execution_policy.capabilities, ("alpha.query",))
            self.assertEqual(manifests[0].execution_policy.entitlements, ("users.username",))

    def test_discovery_does_not_import_plugin_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            plugin_dir = plugins_dir / "alpha"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.py").write_text(
                "raise RuntimeError('discovery imported plugin code')\n",
                encoding="utf-8",
            )
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.query"],
                        "entitlements": [],
                        "entry_point": "plugin:AlphaPlugin",
                        "execution": {
                            "action_type": "informational_read_only",
                            "requires_confirmation": False,
                            "allowed_by_default": True,
                        },
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(errors, [])
            self.assertEqual(len(manifests), 1)

    def test_discovery_infers_fail_closed_policy_for_risky_legacy_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Legacy risky plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "entry_point": "plugin:AlphaPlugin",
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(errors, [])
            self.assertEqual(manifests[0].execution_policy.action_type, "privileged_system_action")
            self.assertTrue(manifests[0].execution_policy.requires_confirmation)
            self.assertFalse(manifests[0].execution_policy.allowed_by_default)

    def test_discovery_rejects_unknown_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["test.capability"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                        "unexpected": "value",
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("Unknown field(s): unexpected", errors[0])

    def test_discovery_rejects_missing_required_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "enabled": True,
                        "capabilities": ["test.capability"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("Missing required field(s): version", errors[0])

    def test_discovery_rejects_missing_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["test.capability"],
                        "entitlements": [],
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("Missing required field(s): runtime", errors[0])

    def test_discovery_rejects_unknown_runtime_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["test.capability"],
                        "entitlements": [],
                        "runtime": {"mode": "sometimes"},
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("runtime.mode must be one of", errors[0])

    def test_discovery_loads_hybrid_runtime_and_database_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Hybrid plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": ["network.local_http"],
                        "runtime": {
                            "mode": "hybrid",
                            "service": {
                                "entry_point": "plugin:AlphaService",
                                "execution_model": "long_running",
                                "start_policy": "auto",
                                "restart_policy": "on_failure",
                                "shutdown_timeout_seconds": 10,
                                "health_check": {
                                    "enabled": True,
                                    "method": "health",
                                    "interval_seconds": 30,
                                    "timeout_seconds": 5,
                                    "failure_threshold": 3,
                                },
                            },
                        },
                        "configuration": {
                            "required": [
                                {
                                    "section": "alpha",
                                    "key": "host",
                                    "type": "string",
                                    "description": "Alpha host.",
                                }
                            ],
                            "optional": [],
                        },
                        "database": {
                            "required": True,
                            "on_missing": "warn_disable",
                            "schemas": [
                                {
                                    "schema_name": "orac_alpha",
                                    "purpose": "Alpha plugin storage.",
                                    "managed_by": "orac",
                                    "minimum_version": "1.0.0",
                                    "version_check": {"enabled": False},
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(errors, [])
            self.assertEqual(manifests[0].runtime_mode, "hybrid")
            self.assertEqual(manifests[0].service_runtime.entry_point, "plugin:AlphaService")
            self.assertEqual(manifests[0].service_runtime.execution_model, "long_running")
            self.assertEqual(manifests[0].configuration_required[0].key, "host")
            self.assertEqual(manifests[0].database_schemas[0].schema_name, "orac_alpha")

    def test_discovery_loads_scheduled_service_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Scheduled plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.sync"],
                        "entitlements": [],
                        "runtime": {
                            "mode": "service",
                            "service": {
                                "entry_point": "plugin:AlphaService",
                                "execution_model": "scheduled",
                                "start_policy": "manual",
                                "restart_policy": "never",
                                "shutdown_timeout_seconds": 10,
                                "schedule": {
                                    "interval_seconds": 60,
                                    "run_on_start": True,
                                    "jitter_seconds": 5,
                                    "timeout_seconds": 30,
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(errors, [])
            service_runtime = manifests[0].service_runtime
            self.assertEqual(service_runtime.execution_model, "scheduled")
            self.assertEqual(service_runtime.schedule.interval_seconds, 60)
            self.assertTrue(service_runtime.schedule.run_on_start)

    def test_discovery_rejects_invalid_service_execution_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Bad service plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.sync"],
                        "entitlements": [],
                        "runtime": {
                            "mode": "service",
                            "service": {
                                "entry_point": "plugin:AlphaService",
                                "execution_model": "daemon",
                                "start_policy": "manual",
                                "restart_policy": "never",
                                "shutdown_timeout_seconds": 10,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("runtime.service.execution_model must be one of", errors[0])

    def test_discovery_rejects_scheduled_service_missing_interval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Bad scheduled plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.sync"],
                        "entitlements": [],
                        "runtime": {
                            "mode": "service",
                            "service": {
                                "entry_point": "plugin:AlphaService",
                                "execution_model": "scheduled",
                                "start_policy": "manual",
                                "restart_policy": "never",
                                "shutdown_timeout_seconds": 10,
                                "schedule": {},
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("runtime.service.schedule missing required field(s): interval_seconds", errors[0])

    def test_discovery_rejects_scheduled_jitter_equal_to_interval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Bad scheduled plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.sync"],
                        "entitlements": [],
                        "runtime": {
                            "mode": "service",
                            "service": {
                                "entry_point": "plugin:AlphaService",
                                "execution_model": "scheduled",
                                "start_policy": "manual",
                                "restart_policy": "never",
                                "shutdown_timeout_seconds": 10,
                                "schedule": {
                                    "interval_seconds": 10,
                                    "jitter_seconds": 10,
                                },
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("jitter_seconds must be less than", errors[0])

    def test_discovery_allows_long_running_service_without_schedule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Long running plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.listen"],
                        "entitlements": [],
                        "runtime": {
                            "mode": "service",
                            "service": {
                                "entry_point": "plugin:AlphaService",
                                "execution_model": "long_running",
                                "start_policy": "manual",
                                "restart_policy": "never",
                                "shutdown_timeout_seconds": 10,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(errors, [])
            self.assertEqual(manifests[0].service_runtime.execution_model, "long_running")
            self.assertIsNone(manifests[0].service_runtime.schedule)

    def test_discovery_rejects_malformed_configuration_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                        "configuration": {
                            "required": [
                                {
                                    "section": "alpha",
                                    "key": "host",
                                    "type": "secret",
                                    "description": "Alpha host.",
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("configuration.required[0].type must be one of", errors[0])

    def test_discovery_rejects_invalid_database_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Database plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.query"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                        "database": {
                            "required": True,
                            "schemas": [
                                {
                                    "schema_name": "orac_alpha",
                                    "purpose": "Alpha plugin storage.",
                                    "managed_by": "external",
                                    "minimum_version": "1.0.0",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifests, errors = PluginDiscovery(plugins_dir).discover()

            self.assertEqual(manifests, [])
            self.assertEqual(len(errors), 1)
            self.assertIn("database.schemas[0].managed_by must be one of: orac", errors[0])

    def test_disabled_plugin_is_not_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            for plugin_id, enabled in (("alpha", True), ("beta", False)):
                (plugins_dir / plugin_id).mkdir()
                (plugins_dir / f"{plugin_id}.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 2,
                            "plugin_id": plugin_id,
                            "name": plugin_id.title(),
                            "description": f"{plugin_id} plugin",
                            "version": "1.0.0",
                            "enabled": enabled,
                            "capabilities": [f"{plugin_id}.capability"],
                            "entitlements": [],
                            "runtime": {"mode": "on_demand"},
                        }
                    ),
                    encoding="utf-8",
                )

            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
            )

            report = manager.refresh()

            self.assertEqual(report["discovered"], 2)
            self.assertEqual(report["valid"], 2)
            self.assertEqual(report["invalid"], 0)
            self.assertEqual(report["enabled"], 1)
            self.assertEqual(report["disabled"], 1)
            self.assertEqual(report["indexed_plugin_count"], 1)
            self.assertIsNone(manager.get_manifest("beta"))

    def test_missing_plugins_directory_does_not_inflate_discovered_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_cache_dir) / "missing_plugins"
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir) / "cache",
            )

            report = manager.refresh()

            self.assertEqual(report["discovered"], 0)
            self.assertEqual(report["valid"], 0)
            self.assertEqual(report["enabled"], 0)
            self.assertEqual(report["invalid"], 1)
            self.assertEqual(len(report["validation_errors"]), 1)

    def test_manager_logs_invalid_manifest_and_refresh_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Bad manifest missing version",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )
            fake_logger = self._FakeLogger()
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=plugins_dir / "cache",
                logger=fake_logger,
            )

            manager.refresh()

            joined = "\n".join(message for _, message in fake_logger.messages)
            self.assertIn("Plugin routing refresh starting", joined)
            self.assertIn("Plugin routing invalid manifest skipped", joined)
            self.assertIn("Plugin routing refresh complete", joined)

    def test_manager_refresh_and_candidate_search(self) -> None:
        provider = HashEmbeddingProvider()
        manager = PluginManager(
            embedding_provider=provider,
            plugins_dir=Path("plugins"),
            cache_dir=Path(tempfile.mkdtemp()),
            database_deployer=_SuccessfulDatabaseDeployer(),
        )

        report = manager.refresh()
        candidates = manager.find_candidates("Turn on the kitchen lights.", top_n=2)

        self.assertEqual(report["embedding_model_id"], provider.model_id)
        self.assertEqual(report["intent_text_version"], INTENT_TEXT_VERSION)
        self.assertEqual(report["discovered"], 3)
        self.assertEqual(report["valid"], 3)
        self.assertEqual(report["invalid"], 0)
        self.assertEqual(report["enabled"], 3)
        self.assertEqual(report["disabled"], 0)
        self.assertEqual(report["dependency_disabled"], 0)
        self.assertEqual(report["indexed_plugin_count"], 8)
        self.assertIsNotNone(manager.get_manifest("home_assistant"))
        self.assertEqual(len(candidates), 2)
        self.assertGreaterEqual(candidates[0].confidence, candidates[1].confidence)
        self.assertTrue(all(candidate.confidence <= 1.0 for candidate in candidates))
        self.assertTrue(all(candidate.capability_id for candidate in candidates))
        self.assertTrue(all(candidate.intent_name for candidate in candidates))

    def test_service_only_plugin_is_not_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Background service",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.service"],
                        "entitlements": [],
                        "runtime": {
                            "mode": "service",
                            "service": {
                                "entry_point": "plugin:AlphaService",
                                "execution_model": "long_running",
                                "start_policy": "manual",
                                "restart_policy": "never",
                                "shutdown_timeout_seconds": 10,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
            )

            report = manager.refresh()

            self.assertEqual(report["valid"], 1)
            self.assertEqual(report["enabled"], 1)
            self.assertEqual(report["indexed_plugin_count"], 0)
            self.assertIsNone(manager.get_manifest("alpha"))

    def test_missing_required_database_schema_disables_plugin_from_routing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Database-backed plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.query"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                        "database": {
                            "required": True,
                            "on_missing": "warn_disable",
                            "schemas": [
                                {
                                    "schema_name": "orac_alpha",
                                    "purpose": "Alpha plugin storage.",
                                    "managed_by": "orac",
                                    "minimum_version": "1.0.0",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
                database_schema_root=Path(temp_cache_dir) / "schema",
            )

            report = manager.refresh()

            self.assertEqual(report["dependency_disabled"], 1)
            self.assertEqual(report["indexed_plugin_count"], 0)
            self.assertIsNone(manager.get_manifest("alpha"))

    def test_missing_required_plugin_config_disables_before_database_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Configured database-backed plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.query"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                        "configuration": {
                            "required": [
                                {
                                    "section": "alpha",
                                    "key": "host",
                                    "type": "string",
                                    "description": "Alpha host.",
                                }
                            ],
                            "optional": [],
                        },
                        "database": {
                            "required": True,
                            "on_missing": "warn_disable",
                            "schemas": [
                                {
                                    "schema_name": "orac_alpha",
                                    "purpose": "Alpha plugin storage.",
                                    "managed_by": "orac",
                                    "minimum_version": "1.0.0",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            deployer = _CountingDatabaseDeployer()
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
                database_deployer=deployer,
            )

            report = manager.refresh()

            self.assertEqual(report["dependency_disabled"], 1)
            self.assertEqual(report["indexed_plugin_count"], 0)
            self.assertEqual(report["configuration_status"]["alpha"], "missing_required")
            self.assertEqual(report["deployment_status"], {})
            self.assertEqual(deployer.calls, [])

    def test_uninitialised_plugin_config_disables_before_database_deployment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            plugin_dir = plugins_dir / "alpha"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.ini").write_text(
                "[alpha]\nhost = %host%\n",
                encoding="utf-8",
            )
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Configured plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.query"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                        "configuration": {
                            "required": [
                                {
                                    "section": "alpha",
                                    "key": "host",
                                    "type": "string",
                                    "description": "Alpha host.",
                                }
                            ],
                            "optional": [],
                        },
                    }
                ),
                encoding="utf-8",
            )
            deployer = _CountingDatabaseDeployer()
            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
                database_deployer=deployer,
            )

            report = manager.refresh()

            self.assertEqual(report["dependency_disabled"], 1)
            self.assertEqual(report["configuration_status"]["alpha"], "uninitialised")
            self.assertEqual(deployer.calls, [])

    def test_cache_invalidation_uses_manifest_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            (plugins_dir / "alpha").mkdir()
            manifest_path = plugins_dir / "alpha.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Initial description",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
            )
            first_report = manager.refresh()
            cache_files_after_first = sorted(Path(temp_cache_dir).glob("*.json"))

            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Updated description",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )
            second_report = manager.refresh()
            cache_files_after_second = sorted(Path(temp_cache_dir).glob("*.json"))

            self.assertEqual(first_report["cache_misses"], 1)
            self.assertEqual(first_report["re_embedded"], 1)
            self.assertEqual(second_report["cache_misses"], 0)
            self.assertEqual(second_report["re_embedded"], 1)
            self.assertEqual(len(cache_files_after_first), 1)
            self.assertEqual(cache_files_after_first, cache_files_after_second)

    def test_cache_filename_sanitises_embedding_model_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            provider = HashEmbeddingProvider(model_id="unsafe/model:id?with spaces")
            manager = PluginManager(
                embedding_provider=provider,
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
            )

            manager.refresh()

            cache_files = list(Path(temp_cache_dir).glob("*.json"))
            self.assertEqual(len(cache_files), 1)
            self.assertNotIn("/", cache_files[0].name)
            self.assertNotIn(":", cache_files[0].name)
            self.assertNotIn(" ", cache_files[0].name)

    def test_separate_cache_file_per_embedding_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Test plugin",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manager_one = PluginManager(
                embedding_provider=HashEmbeddingProvider(model_id="model-one"),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
            )
            manager_two = PluginManager(
                embedding_provider=HashEmbeddingProvider(model_id="model-two"),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
            )

            manager_one.refresh()
            manager_two.refresh()

            cache_files = sorted(Path(temp_cache_dir).glob("*.json"))
            self.assertEqual(len(cache_files), 2)

    def test_cache_hits_on_unchanged_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins_dir, tempfile.TemporaryDirectory() as temp_cache_dir:
            plugins_dir = Path(temp_plugins_dir)
            (plugins_dir / "alpha").mkdir()
            (plugins_dir / "alpha.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "plugin_id": "alpha",
                        "name": "Alpha",
                        "description": "Stable description",
                        "version": "1.0.0",
                        "enabled": True,
                        "capabilities": ["alpha.control"],
                        "entitlements": [],
                        "runtime": {"mode": "on_demand"},
                    }
                ),
                encoding="utf-8",
            )

            manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache_dir),
            )

            manager.refresh()
            second_report = manager.refresh()

            self.assertEqual(second_report["cache_hits"], 1)
            self.assertEqual(second_report["cache_misses"], 0)
            self.assertEqual(second_report["re_embedded"], 0)

    def test_index_normalises_vectors_at_build_and_search_time(self) -> None:
        index = PluginIntentIndex()
        index.build(
            {
                "alpha": [10.0, 0.0],
                "beta": [0.0, 5.0],
            }
        )

        alpha_vector = index._vectors["alpha"]
        beta_vector = index._vectors["beta"]

        self.assertTrue(math.isclose(sum(value * value for value in alpha_vector), 1.0))
        self.assertTrue(math.isclose(sum(value * value for value in beta_vector), 1.0))

        candidates = index.search([20.0, 0.0], top_n=2)

        self.assertEqual(candidates[0].plugin_id, "alpha")
        self.assertGreater(candidates[0].score, candidates[1].score)

    def test_index_rejects_dimension_mismatch(self) -> None:
        index = PluginIntentIndex()
        index.build({"alpha": [1.0, 0.0]})

        with self.assertRaises(ValueError):
            index.search([1.0, 0.0, 0.0], top_n=1)


if __name__ == "__main__":
    unittest.main()
