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
from model.plugin_routing.embeddings import HashEmbeddingProvider
from model.plugin_routing.index import PluginIntentIndex
from model.plugin_routing.intent_text import INTENT_TEXT_VERSION, build_canonical_intent_text
from model.plugin_routing.manager import PluginManager


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
            self.assertNotIn("configuration:", text)
            self.assertNotIn("database:", text)

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
            self.assertEqual(manifests[0].configuration_required[0].key, "host")
            self.assertEqual(manifests[0].database_schemas[0].schema_name, "orac_alpha")

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
        self.assertEqual(report["dependency_disabled"], 1)
        self.assertEqual(report["indexed_plugin_count"], 2)
        self.assertIsNone(manager.get_manifest("home_assistant"))
        self.assertEqual(len(candidates), 2)
        self.assertGreaterEqual(candidates[0].score, candidates[1].score)
        self.assertTrue(all(candidate.score <= 1.0 for candidate in candidates))

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
