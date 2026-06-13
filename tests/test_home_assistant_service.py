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
from home_assistant.control import AreaDevice
from home_assistant.control import HomeAssistantControlError
from home_assistant.control import AreaDeviceList
from home_assistant.control import AreaInventoryRequest
from home_assistant.control import ControlServiceCall
from home_assistant.control import ResolvedControl
from home_assistant.service import HomeAssistantService
from home_assistant.service import HomeAssistantServiceError
from home_assistant.sensor_query import SensorQueryResult
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
    def __init__(
        self,
        config: HomeAssistantClientConfig,
        *,
        fail_check: bool = False,
        fail_fetch_states: bool = False,
        confirmation: list[dict] | None = None,
        states: dict[str, dict] | None = None,
    ) -> None:
        self.config = config
        self.fail_check = fail_check
        self.fail_fetch_states = fail_fetch_states
        self.confirmation = confirmation
        self.states = states or {}
        self.checked = False
        self.closed = False
        self.service_calls: list[tuple[str, str, tuple[str, ...]]] = []
        self.service_call_payloads: list[dict | None] = []
        self.fetch_state_calls: list[str] = []

    def check_api(self) -> bool:
        self.checked = True
        if self.fail_check:
            raise RuntimeError("api unavailable")
        return True

    def close(self) -> None:
        self.closed = True

    def call_service(
        self,
        domain: str,
        service: str,
        entity_ids: tuple[str, ...],
        data: dict | None = None,
    ) -> list[dict]:
        self.service_calls.append((domain, service, entity_ids))
        self.service_call_payloads.append(data)
        if self.confirmation is not None:
            return self.confirmation
        return [{"entity_id": entity_id} for entity_id in entity_ids]

    def fetch_state(self, entity_id: str) -> dict:
        """Return a current sensor state without issuing a service call."""
        self.fetch_state_calls.append(entity_id)
        if self.fail_fetch_states:
            raise RuntimeError("state fetch unavailable")
        if entity_id in self.states:
            return self.states[entity_id]
        return {
            "entity_id": entity_id,
            "state": "21.4",
            "attributes": {
                "device_class": "temperature",
                "unit_of_measurement": "°C",
            },
            "last_changed": "2026-06-12T11:48:00+00:00",
            "last_updated": "2026-06-12T11:48:00+00:00",
        }


class _FakeRepository:
    def __init__(self, context: _FakeContext) -> None:
        self.context = context
        self.closed = False
        self.control_requests: list = []
        self.area_list_requests: list = []
        self.area_inventory_requests: list = []
        self.sensor_query_requests: list = []
        self.sensor_resolution_requests: list = []
        self.cached_sensor_query_requests: list = []

    def close(self) -> None:
        self.closed = True

    def resolve_control(self, request) -> ResolvedControl:
        self.control_requests.append(request)
        return ResolvedControl(
            action=request.action,
            service_calls=(
                ControlServiceCall(
                    domain="light",
                    service=request.action,
                    entity_ids=("light.kitchen",),
                ),
            ),
            target=request.target,
            resolution="entity",
        )

    def list_area(self, request) -> AreaDeviceList:
        self.area_list_requests.append(request)
        return AreaDeviceList(
            area_name=request.area,
            requested_domain=request.requested_domain,
            devices=(
                AreaDevice(
                    name="desk lamp",
                    entity_ids=("switch.desk_lamp",),
                    domains=("switch",),
                ),
            ),
        )

    def list_areas(self, request: AreaInventoryRequest) -> tuple[str, ...]:
        self.area_inventory_requests.append(request)
        return ("office", "kitchen")

    def query_sensors(
        self,
        request,
        *,
        stale_after_hours: float,
        live_states: list[dict],
    ) -> SensorQueryResult:
        self.sensor_query_requests.append((request, stale_after_hours, live_states))
        return SensorQueryResult(
            content=(
                "The Lounge temperature is 21.4°C. That is comfortable. "
                "Home Assistant reports it last updated 12 minutes ago."
            ),
            entity_ids=("sensor.lounge_temperature",),
            areas=("lounge",),
        )

    def resolve_sensor_entities(self, request) -> tuple[str, ...]:
        self.sensor_resolution_requests.append(request)
        if request.intent == "compare_area_temperature":
            return (
                "sensor.lounge_temperature",
                "sensor.landing_temperature",
            )
        return ("sensor.lounge_temperature",)

    def query_cached_sensors(
        self,
        request,
        *,
        stale_after_hours: float,
    ) -> SensorQueryResult:
        self.cached_sensor_query_requests.append((request, stale_after_hours))
        return SensorQueryResult(
            content=(
                "I cannot get a live reading from Home Assistant right now. "
                "Cached Home Assistant data from Orac: The Lounge temperature "
                "is 20.1°C."
            ),
            entity_ids=("sensor.lounge_temperature",),
            areas=("lounge",),
            status="cached",
        )


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

    def test_control_uses_ephemeral_client_and_closes_resources(self) -> None:
        client_holder: dict[str, _FakeClient] = {}
        repository_holder: dict[str, _FakeRepository] = {}

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(config)
            client_holder["client"] = client
            return client

        def repository_factory(context: _FakeContext) -> _FakeRepository:
            repository = _FakeRepository(context)
            repository_holder["repository"] = repository
            return repository

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=repository_factory,
        )

        result = service.handle_command(
            _FakeContext(),
            "control",
            {
                "action": "turn_on",
                "target": "kitchen light",
                "requested_domain": "light",
            },
        )

        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(
            client_holder["client"].service_calls,
            [("light", "turn_on", ("light.kitchen",))],
        )
        self.assertEqual(client_holder["client"].config.timeout_seconds, 5.0)
        self.assertTrue(client_holder["client"].closed)
        self.assertTrue(repository_holder["repository"].closed)
        self.assertFalse(service.state.started)

    def test_control_reports_unconfirmed_without_changing_shadow_state(self) -> None:
        service = HomeAssistantService(
            client_factory=lambda config: _FakeClient(config, confirmation=[]),
            repository_factory=lambda context: _FakeRepository(context),
        )

        result = service.handle_command(
            _FakeContext(),
            "control",
            {"action": "turn_off", "target": "kitchen light"},
        )

        self.assertEqual(result["status"], "unconfirmed")
        self.assertFalse(service.state.started)

    def test_control_validates_required_payload(self) -> None:
        service = HomeAssistantService()

        with self.assertRaisesRegex(ValueError, "action and target"):
            service.handle_command(_FakeContext(), "control", {"action": "turn_on"})

    def test_light_control_sets_brightness_using_live_state(self) -> None:
        client_holder: dict[str, _FakeClient] = {}

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(
                config,
                states={
                    "light.kitchen": {
                        "entity_id": "light.kitchen",
                        "state": "on",
                        "attributes": {
                            "supported_color_modes": ["brightness"],
                            "brightness": 128,
                            "friendly_name": "Kitchen Light",
                        },
                    }
                },
            )
            client_holder["client"] = client
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=lambda context: _FakeRepository(context),
        )

        result = service.handle_command(
            _FakeContext(),
            "light_control",
            {
                "target": "kitchen light",
                "kind": "brightness_pct",
                "value": 50,
                "turn_on": True,
            },
        )

        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(client_holder["client"].fetch_state_calls, ["light.kitchen"])
        self.assertEqual(
            client_holder["client"].service_call_payloads,
            [{"brightness_pct": 50}],
        )
        self.assertEqual(
            client_holder["client"].service_calls,
            [("light", "turn_on", ("light.kitchen",))],
        )
        self.assertIn("Kitchen Light set to 50 percent.", result["content"])

    def test_light_control_uses_live_state_for_relative_brightness(self) -> None:
        client_holder: dict[str, _FakeClient] = {}

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(
                config,
                states={
                    "light.kitchen": {
                        "entity_id": "light.kitchen",
                        "state": "on",
                        "attributes": {
                            "supported_color_modes": ["brightness"],
                            "brightness": 76,
                            "friendly_name": "Kitchen Light",
                        },
                    }
                },
            )
            client_holder["client"] = client
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=lambda context: _FakeRepository(context),
        )

        result = service.handle_command(
            _FakeContext(),
            "light_control",
            {
                "target": "kitchen light",
                "kind": "brightness_step",
                "value": 10,
                "turn_on": True,
            },
        )

        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(
            client_holder["client"].service_call_payloads,
            [{"brightness_pct": 40}],
        )
        self.assertIn("Kitchen Light brightened to 40 percent.", result["content"])

    def test_light_control_refuses_colour_for_brightness_only_light(self) -> None:
        client_holder: dict[str, _FakeClient] = {}

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(
                config,
                states={
                    "light.kitchen": {
                        "entity_id": "light.kitchen",
                        "state": "on",
                        "attributes": {
                            "supported_color_modes": ["brightness"],
                            "brightness": 128,
                            "friendly_name": "Kitchen Light",
                        },
                    }
                },
            )
            client_holder["client"] = client
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=lambda context: _FakeRepository(context),
        )

        with self.assertRaisesRegex(HomeAssistantControlError, "colour control"):
            service.handle_command(
                _FakeContext(),
                "light_control",
                {
                    "target": "kitchen light",
                    "kind": "color_name",
                    "value": "blue",
                    "turn_on": True,
                },
            )

        self.assertEqual(client_holder["client"].service_calls, [])
        self.assertEqual(client_holder["client"].fetch_state_calls, ["light.kitchen"])

    def test_light_control_refuses_switch_domain_lamps_for_richer_commands(self) -> None:
        class _SwitchRepository(_FakeRepository):
            def resolve_control(self, request):
                self.control_requests.append(request)
                return ResolvedControl(
                    action=request.action,
                    service_calls=(
                        ControlServiceCall(
                            domain="switch",
                            service="turn_on",
                            entity_ids=("switch.desk_lamp",),
                        ),
                    ),
                    target=request.target,
                    resolution="entity",
                )

        service = HomeAssistantService(
            client_factory=lambda config: _FakeClient(config),
            repository_factory=lambda context: _SwitchRepository(context),
        )

        with self.assertRaisesRegex(HomeAssistantControlError, "switch"):
            service.handle_command(
                _FakeContext(),
                "light_control",
                {
                    "target": "desk lamp",
                    "kind": "brightness_pct",
                    "value": 50,
                    "turn_on": True,
                },
            )

    def test_light_state_query_reports_live_brightness_and_colour(self) -> None:
        class _TVRepository(_FakeRepository):
            def resolve_control(self, request):
                self.control_requests.append(request)
                return ResolvedControl(
                    action=request.action,
                    service_calls=(
                        ControlServiceCall(
                            domain="light",
                            service="turn_on",
                            entity_ids=("light.tv_light",),
                        ),
                    ),
                    target=request.target,
                    resolution="entity",
                )

        client_holder: dict[str, _FakeClient] = {}

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(
                config,
                states={
                    "light.tv_light": {
                        "entity_id": "light.tv_light",
                        "state": "on",
                        "attributes": {
                            "supported_color_modes": ["hs"],
                            "brightness": 107,
                            "rgb_color": [0, 0, 255],
                            "friendly_name": "TV Light",
                        },
                    }
                },
            )
            client_holder["client"] = client
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=lambda context: _TVRepository(context),
        )

        result = service.handle_command(
            _FakeContext(),
            "light_state_query",
            {
                "intent": "setting",
                "target": "tv light",
                "scope": "entity",
                "requested_domain": "light",
            },
        )

        self.assertEqual(result["status"], "complete")
        self.assertIn("TV Light is on", result["content"])
        self.assertIn("brightness", result["content"])
        self.assertEqual(client_holder["client"].fetch_state_calls, ["light.tv_light"])
        self.assertEqual(client_holder["client"].service_calls, [])

    def test_light_state_query_reports_area_summary_from_live_states(self) -> None:
        class _AreaRepository(_FakeRepository):
            def resolve_control(self, request):
                self.control_requests.append(request)
                return ResolvedControl(
                    action=request.action,
                    service_calls=(
                        ControlServiceCall(
                            domain="light",
                            service="turn_on",
                            entity_ids=(
                                "light.tv_light",
                                "light.floor_lamp",
                                "switch.corner_lamp",
                            ),
                        ),
                    ),
                    target=request.target,
                    resolution="area",
                )

        client_holder: dict[str, _FakeClient] = {}

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(
                config,
                states={
                    "light.tv_light": {
                        "entity_id": "light.tv_light",
                        "state": "on",
                        "attributes": {"friendly_name": "TV Light"},
                    },
                    "light.floor_lamp": {
                        "entity_id": "light.floor_lamp",
                        "state": "on",
                        "attributes": {"friendly_name": "Floor Lamp"},
                    },
                    "switch.corner_lamp": {
                        "entity_id": "switch.corner_lamp",
                        "state": "off",
                        "attributes": {"friendly_name": "Corner Lamp"},
                    },
                },
            )
            client_holder["client"] = client
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=lambda context: _AreaRepository(context),
        )

        result = service.handle_command(
            _FakeContext(),
            "light_state_query",
            {
                "intent": "area_any_on",
                "target": "lounge",
                "scope": "area",
                "requested_domain": "light",
            },
        )

        self.assertEqual(result["status"], "complete")
        self.assertIn("2 Lounge lights are on", result["content"])
        self.assertIn("TV Light", result["content"])
        self.assertIn("Floor Lamp", result["content"])
        self.assertIn("Corner Lamp", result["content"])
        self.assertEqual(
            client_holder["client"].fetch_state_calls,
            ["light.floor_lamp", "light.tv_light", "switch.corner_lamp"],
        )
        self.assertEqual(client_holder["client"].service_calls, [])

    def test_area_listing_uses_only_ephemeral_repository(self) -> None:
        repositories: list[_FakeRepository] = []
        clients: list[_FakeClient] = []

        def repository_factory(context: _FakeContext) -> _FakeRepository:
            repository = _FakeRepository(context)
            repositories.append(repository)
            return repository

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(config)
            clients.append(client)
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=repository_factory,
        )

        result = service.handle_command(
            _FakeContext(),
            "list_area",
            {"area": "office", "requested_domain": "light"},
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["devices"][0]["name"], "desk lamp")
        self.assertEqual(repositories[0].area_list_requests[0].area, "office")
        self.assertTrue(repositories[0].closed)
        self.assertEqual(clients, [])

    def test_area_listing_validates_required_area(self) -> None:
        service = HomeAssistantService()

        with self.assertRaisesRegex(ValueError, "area name"):
            service.handle_command(_FakeContext(), "list_area", {})

    def test_area_inventory_uses_only_shadow_inventory(self) -> None:
        repositories: list[_FakeRepository] = []

        def repository_factory(context: _FakeContext) -> _FakeRepository:
            repository = _FakeRepository(context)
            repositories.append(repository)
            return repository

        service = HomeAssistantService(repository_factory=repository_factory)

        result = service.handle_command(_FakeContext(), "list_areas", {})

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["areas"], ["office", "kitchen"])
        self.assertEqual(len(repositories[0].area_inventory_requests), 1)
        self.assertTrue(repositories[0].closed)

    def test_sensor_query_fetches_live_states_without_service_call(self) -> None:
        repositories: list[_FakeRepository] = []
        clients: list[_FakeClient] = []

        def repository_factory(context: _FakeContext) -> _FakeRepository:
            repository = _FakeRepository(context)
            repositories.append(repository)
            return repository

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(config)
            clients.append(client)
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=repository_factory,
        )

        result = service.handle_command(
            _FakeContext(),
            "sensor_query",
            {
                "intent": "area_temperature",
                "areas": ["lounge"],
                "sensor_role": "temperature",
            },
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["source"], "live_home_assistant")
        self.assertIn("Live Home Assistant reading", result["content"])
        self.assertIn("Lounge temperature", result["content"])
        self.assertIn("Home Assistant reports it last updated", result["content"])
        request, stale_hours, live_states = repositories[0].sensor_query_requests[0]
        self.assertEqual(request.intent, "area_temperature")
        self.assertEqual(stale_hours, 6.0)
        self.assertEqual(live_states[0]["state"], "21.4")
        self.assertTrue(repositories[0].closed)
        self.assertEqual(
            clients[0].fetch_state_calls,
            ["sensor.lounge_temperature"],
        )
        self.assertEqual(clients[0].service_calls, [])
        self.assertEqual(clients[0].config.timeout_seconds, 5.0)
        self.assertTrue(clients[0].closed)

    def test_sensor_query_does_not_fall_back_when_live_fetch_fails(self) -> None:
        repositories: list[_FakeRepository] = []
        clients: list[_FakeClient] = []

        def repository_factory(context: _FakeContext) -> _FakeRepository:
            repository = _FakeRepository(context)
            repositories.append(repository)
            return repository

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(config, fail_fetch_states=True)
            clients.append(client)
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=repository_factory,
        )

        result = service.handle_command(
            _FakeContext(),
            "sensor_query",
            {
                "intent": "area_temperature",
                "areas": ["lounge"],
                "sensor_role": "temperature",
            },
        )

        self.assertEqual(repositories[0].sensor_query_requests, [])
        self.assertEqual(result["status"], "cached")
        self.assertEqual(result["source"], "cached_shadow")
        self.assertIn("cannot get a live reading", result["content"])
        self.assertIn("Cached", result["content"])
        self.assertTrue(repositories[0].closed)
        self.assertTrue(clients[0].closed)
        self.assertEqual(clients[0].service_calls, [])

    def test_comparison_query_fetches_both_resolved_sensor_states(self) -> None:
        clients: list[_FakeClient] = []

        def client_factory(config: HomeAssistantClientConfig) -> _FakeClient:
            client = _FakeClient(config)
            clients.append(client)
            return client

        service = HomeAssistantService(
            client_factory=client_factory,
            repository_factory=lambda context: _FakeRepository(context),
        )

        service.handle_command(
            _FakeContext(),
            "sensor_query",
            {
                "intent": "compare_area_temperature",
                "areas": ["lounge", "landing"],
                "sensor_role": "temperature",
            },
        )

        self.assertEqual(
            clients[0].fetch_state_calls,
            ["sensor.lounge_temperature", "sensor.landing_temperature"],
        )
        self.assertEqual(clients[0].service_calls, [])

    def test_sensor_query_validates_required_intent(self) -> None:
        service = HomeAssistantService()

        with self.assertRaisesRegex(HomeAssistantServiceError, "requires an intent"):
            service.handle_command(_FakeContext(), "sensor_query", {})

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
