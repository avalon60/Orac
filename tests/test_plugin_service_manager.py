"""Tests for Orac-owned plugin service lifecycle management."""
# Author: Clive Bostock
# Date: 2026-05-20
# Description: Verifies service plugin scheduling, cancellation, health, and
#   restart supervision.

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_database_session import PluginDatabaseSessionError
from model.plugin_database_deployment import PluginDatabaseDeploymentResult
from model.plugin_routing.embeddings import HashEmbeddingProvider
from model.plugin_routing.manager import PluginManager
from model.plugin_service_manager import PluginServiceManager


class _SuccessfulDatabaseDeployer:
    def deploy_if_needed(self, manifest):
        status = "deployed" if manifest.database_required else "not_required"
        return PluginDatabaseDeploymentResult(
            plugin_id=manifest.plugin_id,
            status=status,
            eligible=True,
            message="test deployment allowed",
        )


class _FakeLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def log_debug(self, message: str) -> None:
        self.messages.append(("debug", message))

    def log_info(self, message: str) -> None:
        self.messages.append(("info", message))

    def log_warning(self, message: str) -> None:
        self.messages.append(("warning", message))

    def log_error(self, message: str) -> None:
        self.messages.append(("error", message))


def _wait_until(predicate, timeout_seconds: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def _base_manifest(plugin_id: str, runtime: dict, database: dict | None = None) -> dict:
    manifest = {
        "schema_version": 2,
        "plugin_id": plugin_id,
        "name": plugin_id.replace("_", " ").title(),
        "description": "Test service plugin.",
        "version": "1.0.0",
        "enabled": True,
        "capabilities": [f"{plugin_id}.capability"],
        "entitlements": [],
        "entry_point": "plugin:TestPlugin",
        "runtime": runtime,
    }
    if database is not None:
        manifest["database"] = database
    return manifest


def _write_plugin(
    plugins_dir: Path,
    plugin_id: str,
    manifest: dict,
    plugin_code: str,
    *,
    with_schema: bool = False,
) -> None:
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text(plugin_code, encoding="utf-8")
    if with_schema:
        schema_dir = plugin_dir / "db" / "schema" / "table"
        schema_dir.mkdir(parents=True)
        (schema_dir / "example.sql").write_text(
            "create table orac_alpha.example_table (id number);\n",
            encoding="utf-8",
        )
    (plugins_dir / f"{plugin_id}.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def _discover(plugins_dir: Path):
    manifests, errors = PluginDiscovery(plugins_dir).discover()
    if errors:
        raise AssertionError(errors)
    return manifests


def _long_running_runtime(
    *,
    restart_policy: str = "never",
    start_policy: str = "manual",
) -> dict:
    return {
        "mode": "service",
        "service": {
            "entry_point": "plugin:TestService",
            "execution_model": "long_running",
            "start_policy": start_policy,
            "restart_policy": restart_policy,
            "shutdown_timeout_seconds": 1,
            "health_check": {
                "enabled": True,
                "method": "health",
                "interval_seconds": 30,
                "timeout_seconds": 5,
                "failure_threshold": 3,
            },
        },
    }


def _scheduled_runtime(*, interval_seconds: float = 1, run_on_start: bool = True) -> dict:
    return {
        "mode": "service",
        "service": {
            "entry_point": "plugin:TestService",
            "execution_model": "scheduled",
            "start_policy": "manual",
            "restart_policy": "never",
            "shutdown_timeout_seconds": 1,
            "schedule": {
                "interval_seconds": interval_seconds,
                "run_on_start": run_on_start,
            },
        },
    }


LONG_RUNNING_SERVICE_CODE = """
class TestPlugin:
    pass


class TestService:
    def __init__(self, logger=None, config_mgr=None, manifest=None):
        self.context_seen = False

    def run(self, context):
        self.context_seen = hasattr(context, "stop_event")
        while not context.stop_event.wait(0.01):
            pass

    def health(self, context):
        return self.context_seen and not context.stop_event.is_set()
"""


SCHEDULED_SERVICE_CODE = """
class TestPlugin:
    pass


class TestService:
    def tick(self, context):
        return None

    def health(self, context):
        return True
"""


FAILING_SERVICE_CODE = """
class TestPlugin:
    pass


class TestService:
    def run(self, context):
        raise RuntimeError("service failed")
"""


RESTARTING_SERVICE_CODE = """
RUN_COUNT = 0


class TestPlugin:
    pass


class TestService:
    def run(self, context):
        global RUN_COUNT
        RUN_COUNT += 1
        if RUN_COUNT == 1:
            raise RuntimeError("first run failed")
        while not context.stop_event.wait(0.01):
            pass
"""


DB_SESSION_REQUESTING_SERVICE_CODE = """
class TestPlugin:
    pass


class TestService:
    def run(self, context):
        context.plugin_db_session()
"""


SERVICE_COMMAND_CODE = """
class TestPlugin:
    pass


class TestService:
    def __init__(self, logger=None, config_mgr=None, manifest=None):
        self.commands = []

    def run(self, context):
        while not context.stop_event.wait(0.01):
            pass

    def handle_command(self, context, command, payload=None):
        self.commands.append((command, payload or {}))
        return {"command": command, "payload": payload or {}}

    def health(self, context):
        return not context.stop_event.is_set()
"""


def _raise_missing_orac_plugin_credentials():
    raise PluginDatabaseSessionError(
        "ORAC_PLUGIN database credentials are unavailable. Configure saved DSN "
        "connection 'orac-plugin'."
    )


class PluginServiceManagerTests(unittest.TestCase):
    """Tests the Orac-owned plugin service manager."""

    def test_service_only_plugin_is_not_routed_but_is_service_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache:
            plugins_dir = Path(temp_plugins)
            plugin_id = "svc_only"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                LONG_RUNNING_SERVICE_CODE,
            )
            routing_manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())

            routing_report = routing_manager.refresh()
            service_report = service_manager.register_manifests(_discover(plugins_dir))

            self.assertEqual(routing_report["indexed_plugin_count"], 0)
            self.assertEqual(service_report["registered"], 1)
            self.assertEqual(service_manager.service_ids(), (plugin_id,))

    def test_service_with_missing_required_plugin_config_is_not_registered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "svc_config"
            manifest = _base_manifest(plugin_id, _long_running_runtime())
            manifest["configuration"] = {
                "required": [
                    {
                        "section": plugin_id,
                        "key": "host",
                        "type": "string",
                        "description": "Service host.",
                    }
                ],
                "optional": [],
            }
            _write_plugin(
                plugins_dir,
                plugin_id,
                manifest,
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())

            service_report = service_manager.register_manifests(_discover(plugins_dir))

            self.assertEqual(service_report["registered"], 0)
            self.assertEqual(service_report["dependency_invalid"], 1)
            self.assertEqual(service_manager.service_ids(), ())
            self.assertFalse(service_manager.start(plugin_id))

    def test_hybrid_plugin_is_routable_and_service_eligible_when_dependencies_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_cache, tempfile.TemporaryDirectory() as temp_schema:
            plugins_dir = Path(temp_plugins)
            schema_root = Path(temp_schema)
            (schema_root / "orac_alpha").mkdir()
            plugin_id = "hybrid_valid"
            runtime = _long_running_runtime()
            runtime["mode"] = "hybrid"
            database = {
                "required": True,
                "on_missing": "warn_disable",
                "schemas": [
                    {
                        "schema_name": "orac_alpha",
                        "purpose": "Test plugin storage.",
                        "managed_by": "orac",
                        "minimum_version": "1.0.0",
                    }
                ],
            }
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, runtime, database),
                LONG_RUNNING_SERVICE_CODE,
                with_schema=True,
            )
            routing_manager = PluginManager(
                embedding_provider=HashEmbeddingProvider(),
                plugins_dir=plugins_dir,
                cache_dir=Path(temp_cache),
                database_schema_root=schema_root,
                database_deployer=_SuccessfulDatabaseDeployer(),
            )
            service_manager = PluginServiceManager(
                logger=_FakeLogger(),
                database_schema_root=schema_root,
            )

            routing_report = routing_manager.refresh()
            service_report = service_manager.register_manifests(
                list(routing_manager.deployment_eligible_manifests())
            )

            self.assertEqual(routing_report["indexed_plugin_count"], 1)
            self.assertIsNotNone(routing_manager.get_manifest(plugin_id))
            self.assertEqual(service_report["registered"], 1)

    def test_dependency_invalid_hybrid_plugin_is_not_service_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins, tempfile.TemporaryDirectory() as temp_schema:
            plugins_dir = Path(temp_plugins)
            plugin_id = "hybrid_invalid"
            runtime = _long_running_runtime()
            runtime["mode"] = "hybrid"
            database = {
                "required": True,
                "on_missing": "warn_disable",
                "schemas": [
                    {
                        "schema_name": "orac_missing",
                        "purpose": "Missing plugin storage.",
                        "managed_by": "orac",
                        "minimum_version": "1.0.0",
                    }
                ],
            }
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, runtime, database),
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(
                logger=_FakeLogger(),
                database_schema_root=Path(temp_schema),
            )

            report = service_manager.register_manifests(_discover(plugins_dir))

            self.assertEqual(report["registered"], 0)
            self.assertEqual(report["dependency_invalid"], 1)

    def test_disabled_service_plugin_is_discovered_but_not_registered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "disabled_service"
            manifest = _base_manifest(plugin_id, _long_running_runtime(start_policy="auto"))
            manifest["enabled"] = False
            _write_plugin(
                plugins_dir,
                plugin_id,
                manifest,
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())

            report = service_manager.register_manifests(_discover(plugins_dir))

            self.assertEqual(report["registered"], 0)
            self.assertEqual(service_manager.service_ids(), ())

    def test_scheduled_service_tick_is_called_on_start_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "scheduled_start"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(
                    plugin_id,
                    _scheduled_runtime(interval_seconds=1, run_on_start=True),
                ),
                SCHEDULED_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)
            self.assertTrue(
                _wait_until(
                    lambda: service_manager.status()["services"][plugin_id]["tick_count"] >= 1
                )
            )
            service_manager.stop(plugin_id)

            self.assertEqual(service_manager.get_state(plugin_id), "stopped")

    def test_scheduled_service_records_next_interval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "scheduled_interval"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(
                    plugin_id,
                    _scheduled_runtime(interval_seconds=1, run_on_start=True),
                ),
                SCHEDULED_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)
            self.assertTrue(
                _wait_until(
                    lambda: service_manager.status()["services"][plugin_id]["next_run_seconds"] == 1.0
                )
            )
            service_manager.stop(plugin_id)

    def test_long_running_service_receives_context_and_stops_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "long_context"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)
            self.assertTrue(
                _wait_until(lambda: service_manager.check_health(plugin_id))
            )
            service_manager.stop(plugin_id)

            self.assertEqual(service_manager.get_state(plugin_id), "stopped")

    def test_auto_start_services_are_started_under_supervision_and_stop_all_stops_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            auto_plugin_id = "long_auto"
            manual_plugin_id = "long_manual"
            _write_plugin(
                plugins_dir,
                auto_plugin_id,
                _base_manifest(
                    auto_plugin_id,
                    _long_running_runtime(start_policy="auto"),
                ),
                LONG_RUNNING_SERVICE_CODE,
            )
            _write_plugin(
                plugins_dir,
                manual_plugin_id,
                _base_manifest(
                    manual_plugin_id,
                    _long_running_runtime(start_policy="manual"),
                ),
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start_auto_services()
            self.assertTrue(
                _wait_until(
                    lambda: service_manager.get_state(auto_plugin_id) == "running"
                )
            )
            self.assertEqual(service_manager.get_state(manual_plugin_id), "discovered")

            service_manager.stop_all()

            self.assertEqual(service_manager.get_state(auto_plugin_id), "stopped")
            self.assertEqual(service_manager.get_state(manual_plugin_id), "stopped")

    def test_failing_service_transitions_to_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "long_failed"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                FAILING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)
            self.assertTrue(
                _wait_until(lambda: service_manager.get_state(plugin_id) == "failed")
            )

    def test_restart_policy_on_failure_attempts_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "long_restart"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(
                    plugin_id,
                    _long_running_runtime(restart_policy="on_failure"),
                ),
                RESTARTING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)
            self.assertTrue(
                _wait_until(
                    lambda: service_manager.status()["services"][plugin_id]["restart_count"] == 1
                    and service_manager.get_state(plugin_id) == "running"
                )
            )
            service_manager.stop(plugin_id)

    def test_restart_policy_never_does_not_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "long_no_restart"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(
                    plugin_id,
                    _long_running_runtime(restart_policy="never"),
                ),
                FAILING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)
            self.assertTrue(
                _wait_until(lambda: service_manager.get_state(plugin_id) == "failed")
            )
            status = service_manager.status()["services"][plugin_id]
            self.assertEqual(status["restart_count"], 0)

    def test_missing_orac_plugin_credentials_fail_service_startup_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "db_missing_creds"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                DB_SESSION_REQUESTING_SERVICE_CODE,
            )
            service_manager = PluginServiceManager(
                logger=_FakeLogger(),
                plugin_db_session_factory=lambda: (_raise_missing_orac_plugin_credentials()),
            )
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)

            self.assertTrue(
                _wait_until(lambda: service_manager.get_state(plugin_id) == "failed")
            )
            status = service_manager.status()["services"][plugin_id]
            self.assertIn("ORAC_PLUGIN database credentials are unavailable", status["last_error"])
            self.assertNotIn("secret", status["last_error"])

    def test_run_service_command_dispatches_to_managed_service_instance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "commandable"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                SERVICE_COMMAND_CODE,
            )
            service_manager = PluginServiceManager(logger=_FakeLogger())
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)
            self.assertTrue(
                _wait_until(lambda: service_manager.get_state(plugin_id) == "running")
            )

            result = service_manager.run_service_command(
                plugin_id,
                "resync",
                {"source": "unit"},
            )

            self.assertEqual(
                result,
                {"command": "resync", "payload": {"source": "unit"}},
            )
            service_manager.stop(plugin_id)


if __name__ == "__main__":
    unittest.main()
