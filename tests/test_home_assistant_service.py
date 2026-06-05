"""Tests for the managed Home Assistant plugin service."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Verifies Home Assistant service startup sync and lifecycle behaviour.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for path in (SRC_ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from model.plugin_database_deployment import PluginDatabaseDeploymentResult
from model.plugin_routing.embeddings import HashEmbeddingProvider
from model.plugin_routing.manager import PluginManager
from home_assistant.client import HomeAssistantClientConfig
from home_assistant.service import HomeAssistantService
from home_assistant.service import HomeAssistantServiceError
from home_assistant.sync import SyncResult


class _FakeLogger:
    def __init__(self) -> None:
        self.info: list[str] = []
        self.error: list[str] = []

    def log_info(self, message: str) -> None:
        self.info.append(message)

    def log_error(self, message: str) -> None:
        self.error.append(message)


class _FakeConfigManager:
    def __init__(self, values: dict[tuple[str, str], object]) -> None:
        self.values = values

    def config_value(self, section: str, key: str, default=None):
        return self.values.get((section, key), default)

    def int_config_value(self, section: str, key: str, default=None):
        return int(self.config_value(section, key, default))

    def bool_config_value(self, section: str, key: str, default=None):
        value = self.config_value(section, key, default)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}


class _FakeSecretVault:
    def __init__(self, token: str | None = "secret-token") -> None:
        self.token = token
        self.keys_requested: list[str] = []

    def get(self, key: str = "access_token") -> str:
        self.keys_requested.append(key)
        if self.token is None:
            raise RuntimeError(
                "Plugin personal access token is not configured. Create it with: "
                "bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token"
            )
        return self.token


class _FakeContext:
    def __init__(
        self,
        config_mgr: _FakeConfigManager | None = None,
        secret_vault: _FakeSecretVault | None = None,
    ) -> None:
        self.stop_event = threading.Event()
        self.repository_session_requested = False
        self.config_mgr = config_mgr or _valid_config()
        self.secret_vault = secret_vault or _FakeSecretVault()

    def plugin_db_session(self):
        self.repository_session_requested = True
        return object()

    def plugin_config(self):
        return self.config_mgr


class _FakeClient:
    def __init__(self, config: HomeAssistantClientConfig, *, fail_check: bool = False) -> None:
        self.config = config
        self.fail_check = fail_check
        self.checked = False
        self.closed = False

    def check_api(self) -> bool:
        self.checked = True
        if self.fail_check:
            raise RuntimeError("api unavailable")
        return True

    def close(self) -> None:
        self.closed = True


class _FakeRepository:
    def __init__(self, context: _FakeContext) -> None:
        self.context = context
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeSyncCoordinator:
    def __init__(self, *, client: _FakeClient, repository: _FakeRepository, fail: bool = False) -> None:
        self.client = client
        self.repository = repository
        self.fail = fail
        self.called = False

    def run_initial_sync(self):
        self.called = True
        if self.fail:
            raise RuntimeError("sync failed")
        started = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
        completed = datetime(2026, 6, 4, 12, 1, tzinfo=UTC)
        return (
            SyncResult("structural", "structural-run", 3, started, completed),
            SyncResult("state", "state-run", 1, started, completed),
        )


class _SuccessfulDatabaseDeployer:
    def deploy_if_needed(self, manifest):
        status = "deployed" if manifest.database_required else "not_required"
        return PluginDatabaseDeploymentResult(
            plugin_id=manifest.plugin_id,
            status=status,
            eligible=True,
            message="test deployment allowed",
        )


def _valid_config() -> _FakeConfigManager:
    return _FakeConfigManager(
        {
            ("home_assistant", "host"): "ha.local",
            ("home_assistant", "port"): "8123",
            ("home_assistant", "protocol"): "http",
            ("home_assistant", "verify_ssl"): False,
        }
    )


class HomeAssistantServiceTests(unittest.TestCase):
    """Tests Home Assistant service lifecycle behaviour."""

    def test_refuses_to_start_when_host_is_missing(self) -> None:
        config = _valid_config()
        config.values[("home_assistant", "host")] = ""
        service = HomeAssistantService()

        with self.assertRaisesRegex(HomeAssistantServiceError, "host"):
            service.run(_FakeContext(config))

    def test_refuses_to_start_when_port_is_missing(self) -> None:
        config = _valid_config()
        config.values[("home_assistant", "port")] = ""
        service = HomeAssistantService()

        with self.assertRaisesRegex(HomeAssistantServiceError, "port"):
            service.run(_FakeContext(config))

    def test_refuses_to_start_when_pat_vault_is_missing(self) -> None:
        service = HomeAssistantService()

        context = _FakeContext()
        delattr(context, "secret_vault")
        with self.assertRaisesRegex(HomeAssistantServiceError, "plugin-pat-mgr.sh"):
            service.run(context)

    def test_refuses_to_start_when_pat_token_is_missing(self) -> None:
        logger = _FakeLogger()
        service = HomeAssistantService(logger=logger)

        with self.assertRaisesRegex(RuntimeError, "plugin-pat-mgr.sh"):
            service.run(_FakeContext(secret_vault=_FakeSecretVault(None)))

        log_text = "\n".join(logger.info + logger.error)
        self.assertNotIn("secret-token", log_text)

    def test_token_value_is_not_logged(self) -> None:
        logger = _FakeLogger()
        secret_value = "super-secret-ha-token"
        service = HomeAssistantService(
            logger=logger,
            client_factory=lambda config: _FakeClient(config, fail_check=True),
            repository_factory=lambda context: _FakeRepository(context),
            sync_coordinator_factory=lambda **kwargs: _FakeSyncCoordinator(**kwargs),
        )

        with self.assertRaisesRegex(RuntimeError, "api unavailable"):
            service.run(_FakeContext(secret_vault=_FakeSecretVault(secret_value)))

        log_text = "\n".join(logger.info + logger.error)
        self.assertIn("PAT vault", log_text)
        self.assertNotIn(secret_value, log_text)

    def test_successful_startup_sync_blocks_until_stopped_and_reports_health(self) -> None:
        context = _FakeContext()
        logger = _FakeLogger()
        client_holder: dict[str, _FakeClient] = {}
        repository_holder: dict[str, _FakeRepository] = {}
        sync_holder: dict[str, _FakeSyncCoordinator] = {}

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(config)
            client_holder["client"] = client
            return client

        def repository_factory(runtime_context: _FakeContext) -> _FakeRepository:
            repository = _FakeRepository(runtime_context)
            repository_holder["repository"] = repository
            return repository

        def sync_factory(**kwargs) -> _FakeSyncCoordinator:
            coordinator = _FakeSyncCoordinator(**kwargs)
            sync_holder["sync"] = coordinator
            return coordinator

        service = HomeAssistantService(
            logger=logger,
            client_factory=client_factory,
            repository_factory=repository_factory,
            sync_coordinator_factory=sync_factory,
        )
        errors: list[BaseException] = []

        def run_service() -> None:
            try:
                service.run(context)
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=run_service)
        thread.start()
        self.assertTrue(_wait_until(lambda: service.state.started))
        self.assertTrue(service.health(context))
        service.stop(context)
        thread.join(timeout=1)

        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(client_holder["client"].checked)
        self.assertEqual(client_holder["client"].config.host, "ha.local")
        self.assertEqual(client_holder["client"].config.token, "secret-token")
        self.assertFalse(client_holder["client"].config.verify_ssl)
        self.assertTrue(sync_holder["sync"].called)
        self.assertIs(repository_holder["repository"].context, context)
        self.assertFalse(service.health(context))

    def test_startup_uses_context_plugin_config_not_constructor_config(self) -> None:
        context_config = _valid_config()
        context_config.values[("home_assistant", "host")] = "context-ha.local"
        constructor_config = _valid_config()
        constructor_config.values[("home_assistant", "host")] = "global-ha.local"
        client_holder: dict[str, _FakeClient] = {}

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(config)
            client_holder["client"] = client
            return client

        service = HomeAssistantService(
            config_mgr=constructor_config,
            client_factory=client_factory,
            repository_factory=lambda runtime_context: _FakeRepository(runtime_context),
            sync_coordinator_factory=lambda **kwargs: _FakeSyncCoordinator(**kwargs),
        )

        service.handle_command(_FakeContext(context_config), "resync", {"source": "unit"})

        self.assertEqual(client_holder["client"].config.host, "context-ha.local")

    def test_sync_failure_marks_unhealthy_and_raises_for_restart_policy(self) -> None:
        service = HomeAssistantService(
            client_factory=lambda config: _FakeClient(config),
            repository_factory=lambda context: _FakeRepository(context),
            sync_coordinator_factory=lambda **kwargs: _FakeSyncCoordinator(
                **kwargs,
                fail=True,
            ),
        )

        with self.assertRaisesRegex(RuntimeError, "sync failed"):
            service.run(_FakeContext())

        self.assertFalse(service.state.started)
        self.assertIn("sync failed", service.state.last_error)
        self.assertEqual(service.state.structural_sync_status, "failed")
        self.assertEqual(service.state.state_sync_status, "failed")

    def test_handle_resync_command_runs_existing_sync_path(self) -> None:
        context = _FakeContext()
        sync_holder: dict[str, _FakeSyncCoordinator] = {}

        def sync_factory(**kwargs) -> _FakeSyncCoordinator:
            coordinator = _FakeSyncCoordinator(**kwargs)
            sync_holder["sync"] = coordinator
            return coordinator

        service = HomeAssistantService(
            client_factory=lambda config: _FakeClient(config),
            repository_factory=lambda runtime_context: _FakeRepository(runtime_context),
            sync_coordinator_factory=sync_factory,
        )

        result = service.handle_command(context, "resync", {"source": "unit"})

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["structural_rows"], 3)
        self.assertEqual(result["state_rows"], 1)
        self.assertTrue(sync_holder["sync"].called)
        self.assertTrue(service.state.started)
        self.assertEqual(service.state.structural_sync_status, "complete")
        self.assertEqual(service.state.state_sync_status, "complete")

    def test_plugin_manager_refresh_does_not_call_home_assistant_api(self) -> None:
        with tempfile.TemporaryDirectory() as temp_cache:
            with patch("home_assistant.client.HomeAssistantClient") as client_class:
                manager = PluginManager(
                    embedding_provider=HashEmbeddingProvider(),
                    plugins_dir=Path("plugins"),
                    cache_dir=Path(temp_cache),
                    database_deployer=_SuccessfulDatabaseDeployer(),
                )

                manager.refresh()

        client_class.assert_not_called()


def _wait_until(predicate, timeout_seconds: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


if __name__ == "__main__":
    unittest.main()
