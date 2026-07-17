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
from types import SimpleNamespace
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


class _LifecycleStore:
    """In-memory service lifecycle store for manager unit tests."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], SimpleNamespace] = {}
        self.tokens: dict[tuple[str, str], str] = {}
        self.active_owner: dict[tuple[str, str], str | None] = {}
        self.active_token: dict[tuple[str, str], str | None] = {}
        self.heartbeat_failures: set[tuple[str, str]] = set()
        self.release_calls: list[tuple[str, str, str | None]] = []

    def register_service(
        self,
        *,
        plugin_id,
        service_code,
        service_name,
        entry_point,
        execution_model,
        manifest_policy,
    ):
        key = (plugin_id, service_code)
        row = self.rows.get(key)
        if row is None:
            row = SimpleNamespace(
                plugin_id=plugin_id,
                service_code=service_code,
                service_name=service_name,
                entry_point=entry_point,
                execution_model=execution_model,
                manifest_policy=manifest_policy,
                effective_policy=manifest_policy,
                current_state="disabled" if manifest_policy == "disabled" else "registered",
                row_version=1,
            )
            self.rows[key] = row
        else:
            row.manifest_policy = manifest_policy
            if getattr(row, "policy_override", None) is None:
                row.effective_policy = manifest_policy
            if row.effective_policy == "disabled":
                row.current_state = "disabled"
        return row

    def try_acquire_lease(self, *, plugin_id, service_code, owner_id, lease_seconds):
        key = (plugin_id, service_code)
        active_owner = self.active_owner.get(key)
        if active_owner and active_owner != owner_id:
            return None
        token = self.tokens.get(key) or f"token-{plugin_id}-{service_code}"
        self.tokens[key] = token
        self.active_owner[key] = owner_id
        self.active_token[key] = token
        row = self.rows[key]
        row.current_state = "starting"
        return token

    def heartbeat_lease(self, *, plugin_id, service_code, owner_id, lease_token, lease_seconds):
        key = (plugin_id, service_code)
        if key in self.heartbeat_failures:
            return False
        return (
            self.active_owner.get(key) == owner_id
            and self.active_token.get(key) == lease_token
        )

    def release_lease(self, *, plugin_id, service_code, owner_id, lease_token):
        key = (plugin_id, service_code)
        self.release_calls.append((plugin_id, service_code, lease_token))
        if (
            self.active_owner.get(key) == owner_id
            and self.active_token.get(key) == lease_token
        ):
            self.active_owner[key] = None
            self.active_token[key] = None
            self.rows[key].current_state = "stopped"
            return True
        return False

    def mark_state(
        self,
        *,
        plugin_id,
        service_code,
        owner_id,
        lease_token,
        state,
        last_error_message=None,
        touch_tick=False,
    ):
        key = (plugin_id, service_code)
        if (
            self.active_owner.get(key) != owner_id
            or self.active_token.get(key) != lease_token
        ):
            return False
        self.rows[key].current_state = state
        self.rows[key].last_error_message = last_error_message
        return True


class _BusyOnceLifecycleStore(_LifecycleStore):
    """Lifecycle store that reports one busy lease before acquiring."""

    def __init__(self) -> None:
        """Initialise an in-memory store with acquisition counters."""
        super().__init__()
        self.acquire_attempts: dict[tuple[str, str], int] = {}

    def try_acquire_lease(self, *, plugin_id, service_code, owner_id, lease_seconds):
        key = (plugin_id, service_code)
        self.acquire_attempts[key] = self.acquire_attempts.get(key, 0) + 1
        if self.acquire_attempts[key] == 1:
            return None
        return super().try_acquire_lease(
            plugin_id=plugin_id,
            service_code=service_code,
            owner_id=owner_id,
            lease_seconds=lease_seconds,
        )


def _service_manager(**kwargs) -> PluginServiceManager:
    return PluginServiceManager(
        logger=kwargs.pop("logger", _FakeLogger()),
        lifecycle_store=kwargs.pop("lifecycle_store", _LifecycleStore()),
        heartbeat_interval_seconds=kwargs.pop("heartbeat_interval_seconds", 0.02),
        lease_seconds=kwargs.pop("lease_seconds", 1),
        **kwargs,
    )


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
            service_manager = _service_manager()

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
            service_manager = _service_manager()

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
            service_manager = _service_manager(
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
            service_manager = _service_manager(
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
            service_manager = _service_manager()

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
            service_manager = _service_manager()
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
            service_manager = _service_manager()
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
            service_manager = _service_manager()
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
            service_manager = _service_manager()
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start_auto_services()
            self.assertTrue(
                _wait_until(
                    lambda: service_manager.get_state(auto_plugin_id) == "running"
                )
            )
            self.assertEqual(service_manager.get_state(manual_plugin_id), "registered")

            service_manager.stop_all_services()

            self.assertEqual(service_manager.get_state(auto_plugin_id), "stopped")
            self.assertEqual(service_manager.get_state(manual_plugin_id), "stopped")

    def test_disabled_policy_registers_but_does_not_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "long_disabled"
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(
                    plugin_id,
                    _long_running_runtime(start_policy="disabled"),
                ),
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = _service_manager()
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start_auto_services()

            self.assertEqual(service_manager.get_state(plugin_id), "disabled")
            self.assertFalse(service_manager.start(plugin_id))

    def test_active_external_lease_prevents_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "leased_elsewhere"
            lifecycle_store = _LifecycleStore()
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = _service_manager(
                lifecycle_store=lifecycle_store,
                owner_id="unit-owner",
            )
            service_manager.register_manifests(_discover(plugins_dir))
            lifecycle_store.active_owner[(plugin_id, "default")] = "other-owner"
            lifecycle_store.active_token[(plugin_id, "default")] = "other-token"

            self.assertFalse(service_manager.start(plugin_id))
            self.assertEqual(service_manager.get_state(plugin_id), "registered")

    def test_busy_restart_lease_is_retried_before_start_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "retry_lease"
            lifecycle_store = _BusyOnceLifecycleStore()
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = _service_manager(
                lifecycle_store=lifecycle_store,
                owner_id="unit-owner",
                lease_acquire_retry_seconds=0.2,
                lease_acquire_retry_interval_seconds=0.01,
                sleep_func=lambda _seconds: None,
            )
            service_manager.register_manifests(_discover(plugins_dir))

            self.assertTrue(service_manager.start(plugin_id))
            self.assertEqual(
                lifecycle_store.acquire_attempts[(plugin_id, "default")],
                2,
            )
            self.assertTrue(
                _wait_until(lambda: service_manager.get_state(plugin_id) == "running")
            )
            service_manager.stop(plugin_id)

    def test_stale_or_released_lease_can_be_acquired(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "lease_recovered"
            lifecycle_store = _LifecycleStore()
            lifecycle_store.active_owner[(plugin_id, "default")] = None
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = _service_manager(
                lifecycle_store=lifecycle_store,
                owner_id="unit-owner",
            )
            service_manager.register_manifests(_discover(plugins_dir))

            self.assertTrue(service_manager.start(plugin_id))
            self.assertTrue(_wait_until(lambda: service_manager.get_state(plugin_id) == "running"))
            service_manager.stop(plugin_id)

            self.assertEqual(
                lifecycle_store.release_calls[-1],
                (plugin_id, "default", f"token-{plugin_id}-default"),
            )

    def test_heartbeat_loss_transitions_to_lease_lost(self) -> None:
        with tempfile.TemporaryDirectory() as temp_plugins:
            plugins_dir = Path(temp_plugins)
            plugin_id = "lease_lost"
            lifecycle_store = _LifecycleStore()
            _write_plugin(
                plugins_dir,
                plugin_id,
                _base_manifest(plugin_id, _long_running_runtime()),
                LONG_RUNNING_SERVICE_CODE,
            )
            service_manager = _service_manager(
                lifecycle_store=lifecycle_store,
                owner_id="unit-owner",
                heartbeat_interval_seconds=0.01,
            )
            service_manager.register_manifests(_discover(plugins_dir))

            service_manager.start(plugin_id)
            self.assertTrue(_wait_until(lambda: service_manager.get_state(plugin_id) == "running"))
            lifecycle_store.heartbeat_failures.add((plugin_id, "default"))

            self.assertTrue(
                _wait_until(
                    lambda: "lease_lost"
                    in service_manager.status()["services"][plugin_id]["state_history"]
                )
            )
            service_manager.stop(plugin_id)

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
            service_manager = _service_manager()
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
            service_manager = _service_manager()
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
            service_manager = _service_manager()
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
            service_manager = _service_manager(
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
            service_manager = _service_manager()
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
