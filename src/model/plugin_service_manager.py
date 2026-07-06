"""Orac-owned lifecycle manager for service-capable plugins."""
# Author: Clive Bostock
# Date: 2026-05-20
# Description: Provides supervised service plugin execution without allowing
#   plugins to own unmanaged background loops.

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import os
from pathlib import Path
import random
import socket
import threading
import time
import uuid
from typing import Any, Callable, Protocol

from lib.fsutils import project_home
from model.plugin_config import PluginConfigManager
from model.plugin_database_deployment import plugin_schema_payload_path
from model.plugin_database_session import OracPluginDatabaseSession
from model.plugin_database_session import OracPluginDatabaseSessionFactory
from model.plugin_routing.models import PluginServiceRuntime
from model.plugin_routing.models import PluginManifest
from model.plugin_runtime import PluginRuntimeError, load_plugin_service_class
from model.plugin_secret_vault import PluginSecretVault
from model.plugin_service_lifecycle import PluginServiceLifecycleStore


PLUGIN_SERVICE_STATES = {
    "discovered",
    "registered",
    "starting",
    "running",
    "unhealthy",
    "stopping",
    "stopped",
    "failed",
    "disabled",
    "lease_lost",
}


class ScheduledPluginService(Protocol):
    """Protocol for scheduled service plugin implementations."""

    def tick(self, context: "PluginServiceContext") -> None:
        """Run one Orac-scheduled unit of service work."""


class LongRunningPluginService(Protocol):
    """Protocol for long-running service plugin implementations."""

    def run(self, context: "PluginServiceContext") -> None:
        """Run until the Orac-owned stop event is set."""


@dataclass(frozen=True)
class PluginServiceContext:
    """Small context object exposed to service plugin implementations."""

    plugin_id: str
    service_code: str
    logger: Any
    stop_event: threading.Event
    manifest: PluginManifest
    config_mgr: Any | None = None
    plugin_config_manager: PluginConfigManager | None = None
    _plugin_db_session_factory: Callable[[], OracPluginDatabaseSession] | None = None
    _secret_vault: PluginSecretVault | None = None

    def plugin_db_session(self) -> OracPluginDatabaseSession:
        """Return a managed ORAC_PLUGIN database session for plugin runtime use."""
        if self._plugin_db_session_factory is None:
            raise PluginRuntimeError(
                f"Plugin '{self.plugin_id}' requested database access, but no "
                "managed plugin database session factory is configured."
            )
        return self._plugin_db_session_factory()

    def plugin_config(self) -> PluginConfigManager:
        """Return this plugin's scoped configuration manager."""
        if self.plugin_config_manager is None:
            raise PluginRuntimeError(
                f"Plugin '{self.plugin_id}' requested configuration access, but no "
                "plugin configuration manager is configured."
            )
        return self.plugin_config_manager

    @property
    def secret_vault(self) -> PluginSecretVault:
        """Return this plugin's scoped personal access token vault."""
        if self._secret_vault is None:
            return PluginSecretVault(plugin_id=self.plugin_id, manifest=self.manifest)
        return self._secret_vault


@dataclass
class _ServiceRecord:
    """Internal state for one registered service plugin."""

    manifest: PluginManifest
    service_runtime: PluginServiceRuntime
    service_id: str
    effective_policy: str = "manual"
    state: str = "discovered"
    context: PluginServiceContext | None = None
    instance: Any | None = None
    thread: threading.Thread | None = None
    heartbeat_thread: threading.Thread | None = None
    lease_token: str | None = None
    restart_count: int = 0
    last_error: str | None = None
    tick_count: int = 0
    next_run_seconds: float | None = None
    state_history: list[str] = field(default_factory=lambda: ["discovered"])


class PluginServiceManager:
    """Owns lifecycle, scheduling, cancellation, and health for service plugins."""

    def __init__(
        self,
        *,
        logger: Any,
        config_mgr: Any | None = None,
        database_schema_root: Path | None = None,
        service_loader: Callable[..., type] = load_plugin_service_class,
        plugin_db_session_factory: Callable[[], OracPluginDatabaseSession] | None = None,
        lifecycle_store: Any | None = None,
        owner_id: str | None = None,
        max_restart_attempts: int = 1,
        lease_seconds: int = 30,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        self._logger = logger
        self._config_mgr = config_mgr
        self._project_root = project_home()
        self._database_schema_root = (
            Path(database_schema_root)
            if database_schema_root
            else self._project_root / "resources" / "db" / "schema"
        )
        self._service_loader = service_loader
        self.owner_id = owner_id or _default_owner_id()
        self._lifecycle_store = lifecycle_store or PluginServiceLifecycleStore()
        self._plugin_db_session_factory = (
            plugin_db_session_factory
            or OracPluginDatabaseSessionFactory(
                config_mgr=config_mgr,
                logger=logger,
            ).create
        )
        self._max_restart_attempts = max_restart_attempts
        self._lease_seconds = lease_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._records: dict[tuple[str, str], _ServiceRecord] = {}
        self._dependency_invalid: dict[str, PluginManifest] = {}

    def register_manifests(self, manifests: list[PluginManifest]) -> dict[str, Any]:
        """Register enabled, dependency-valid service or hybrid manifests."""
        self._dependency_invalid.clear()
        seen_keys: set[tuple[str, str]] = set()

        for manifest in manifests:
            if manifest.runtime_mode not in {"service", "hybrid"}:
                continue
            if not manifest.enabled:
                self._log_info(
                    f"Plugin service '{manifest.plugin_id}' skipped because manifest is disabled."
                )
                continue
            service_runtimes = manifest.service_runtimes or (
                (manifest.service_runtime,) if manifest.service_runtime is not None else ()
            )
            if not service_runtimes:
                self._log_error(
                    f"Plugin service '{manifest.plugin_id}' skipped because runtime.service is missing."
                )
                continue
            config_result = PluginConfigManager(
                manifest,
                logger=self._logger,
            ).validate()
            if not config_result.eligible:
                self._dependency_invalid[manifest.plugin_id] = manifest
                detail_keys = config_result.missing_keys or config_result.uninitialised_keys
                detail_text = ", ".join(detail_keys) if detail_keys else "unknown"
                self._log_warning(
                    "Plugin service skipped enabled plugin "
                    f"'{manifest.plugin_id}' because plugin configuration status is "
                    f"{config_result.status}: {config_result.message} "
                    f"Affected key(s): {detail_text}"
                )
                continue
            if self._has_missing_database_schema(manifest):
                if manifest.database_on_missing == "fail_refresh":
                    raise RuntimeError(
                        "Plugin service registration failed because plugin "
                        f"'{manifest.plugin_id}' is missing required database schema metadata."
                    )
                if manifest.database_on_missing == "warn_disable":
                    self._dependency_invalid[manifest.plugin_id] = manifest
                    self._log_warning(
                        "Plugin service skipped enabled plugin "
                        f"'{manifest.plugin_id}' because required database schema "
                        "metadata is unavailable."
                    )
                    continue
            for service_runtime in service_runtimes:
                key = (manifest.plugin_id, service_runtime.service_code)
                seen_keys.add(key)
                service_id = _service_id(*key)
                status = self._lifecycle_store.register_service(
                    plugin_id=manifest.plugin_id,
                    service_code=service_runtime.service_code,
                    service_name=manifest.name,
                    entry_point=service_runtime.entry_point,
                    execution_model=service_runtime.execution_model,
                    manifest_policy=service_runtime.start_policy,
                )
                record = self._records.get(key)
                if record is None:
                    self._records[key] = _ServiceRecord(
                        manifest=manifest,
                        service_runtime=service_runtime,
                        service_id=service_id,
                        effective_policy=status.effective_policy,
                        state=status.current_state,
                        state_history=[status.current_state],
                    )
                    self._log_info(f"Plugin service '{service_id}' discovered.")
                else:
                    record.manifest = manifest
                    record.service_runtime = service_runtime
                    record.effective_policy = status.effective_policy
                    if record.thread is None or not record.thread.is_alive():
                        self._transition(record, status.current_state)

        for key, record in list(self._records.items()):
            if key not in seen_keys and record.thread is not None and record.thread.is_alive():
                self.stop(record.manifest.plugin_id, record.service_runtime.service_code)
            if key not in seen_keys:
                del self._records[key]

        return self.status()

    def start_auto_services(self) -> None:
        """Start all registered services whose start policy is auto."""
        for key, record in list(self._records.items()):
            if record.effective_policy == "auto":
                self.start(*key)
            elif record.effective_policy == "disabled":
                self._transition(record, "disabled")
                self._log_info(
                    f"Plugin service '{record.service_id}' is disabled; not auto-started."
                )
            else:
                self._log_info(
                    f"Plugin service '{record.service_id}' discovered with manual start policy; not auto-started."
                )

    def start(self, plugin_id: str, service_code: str | None = None) -> bool:
        """Start a registered plugin service."""
        key = self._resolve_service_key(plugin_id, service_code)
        record = self._records.get(key) if key is not None else None
        if record is None:
            self._log_warning(f"Plugin service '{plugin_id}' was not registered.")
            return False
        if record.effective_policy == "disabled":
            self._transition(record, "disabled")
            self._log_warning(f"Plugin service '{record.service_id}' is disabled.")
            return False
        if record.thread is not None and record.thread.is_alive():
            self._log_debug(f"Plugin service '{record.service_id}' is already running.")
            return True

        lease_token = self._lifecycle_store.try_acquire_lease(
            plugin_id=record.manifest.plugin_id,
            service_code=record.service_runtime.service_code,
            owner_id=self.owner_id,
            lease_seconds=self._lease_seconds,
        )
        if not lease_token:
            self._log_warning(
                f"Plugin service '{record.service_id}' could not acquire its lease."
            )
            return False
        record.lease_token = lease_token
        self._transition(record, "starting")
        try:
            self._prepare_record(record)
            thread = threading.Thread(
                target=self._run_service,
                args=(record,),
                name=f"orac-plugin-service-{record.service_id}",
                daemon=False,
            )
            record.thread = thread
            thread.start()
            self._start_heartbeat(record)
            return True
        except Exception as exc:
            record.last_error = str(exc)
            self._transition(record, "failed")
            self._release_lease(record)
            self._log_exception(f"Plugin service '{record.service_id}' failed to start", exc)
            return False

    def stop(self, plugin_id: str, service_code: str | None = None) -> bool:
        """Request cancellation and wait up to the service shutdown timeout."""
        key = self._resolve_service_key(plugin_id, service_code)
        record = self._records.get(key) if key is not None else None
        if record is None:
            self._log_warning(f"Plugin service '{plugin_id}' was not registered.")
            return False

        service_runtime = record.service_runtime
        timeout_seconds = service_runtime.shutdown_timeout_seconds if service_runtime else 1
        self._transition(record, "stopping")
        self._persist_state(record, "stopping")
        if record.context is not None:
            record.context.stop_event.set()
        if record.instance is not None and hasattr(record.instance, "stop"):
            try:
                record.instance.stop(record.context)
            except Exception as exc:
                record.last_error = str(exc)
                self._log_exception(
                    f"Plugin service '{record.service_id}' stop hook failed",
                    exc,
                )

        if record.thread is not None:
            record.thread.join(timeout=timeout_seconds)
            if record.thread.is_alive():
                record.last_error = (
                    f"Service did not stop within {timeout_seconds} seconds."
                )
                self._transition(record, "failed")
                self._persist_state(record, "failed", record.last_error)
                self._log_error(
                    f"Plugin service '{record.service_id}' did not stop within "
                    f"{timeout_seconds} seconds."
                )
                return False

        self._persist_state(record, "stopped")
        self._release_lease(record)
        self._transition(record, "stopped")
        self._log_info(f"Plugin service '{record.service_id}' stopped.")
        return True

    def stop_all_services(self) -> None:
        """Stop all registered plugin services."""
        for plugin_id, service_code in list(self._records):
            self.stop(plugin_id, service_code)

    def stop_all(self) -> None:
        """Backward-compatible alias for stopping all plugin services."""
        self.stop_all_services()

    def check_health(self, plugin_id: str, service_code: str | None = None) -> bool:
        """Run a plugin service health check when the service exposes one."""
        key = self._resolve_service_key(plugin_id, service_code)
        record = self._records.get(key) if key is not None else None
        if record is None or record.instance is None:
            return False
        if not hasattr(record.instance, "health"):
            return record.state == "running"
        try:
            healthy = bool(record.instance.health(record.context))
        except Exception as exc:
            record.last_error = str(exc)
            self._transition(record, "unhealthy")
            self._log_exception(f"Plugin service '{record.service_id}' health check failed", exc)
            return False
        if healthy:
            if record.state == "unhealthy":
                self._transition(record, "running")
            return True
        self._transition(record, "unhealthy")
        self._log_warning(f"Plugin service '{record.service_id}' reported unhealthy.")
        return False

    def run_service_command(
        self,
        plugin_id: str,
        command: str,
        payload: dict[str, Any] | None = None,
        service_code: str | None = None,
    ) -> Any:
        """Run a command on a registered Orac-managed plugin service."""
        key = self._resolve_service_key(plugin_id, service_code)
        record = self._records.get(key) if key is not None else None
        if record is None:
            raise PluginRuntimeError(f"Plugin service '{plugin_id}' was not registered.")
        if record.instance is None or record.context is None:
            raise PluginRuntimeError(f"Plugin service '{plugin_id}' is not started.")
        if record.state not in {"running", "unhealthy"}:
            raise PluginRuntimeError(
                f"Plugin service '{plugin_id}' is not commandable while {record.state}."
            )
        handle_command = getattr(record.instance, "handle_command", None)
        if not callable(handle_command):
            raise PluginRuntimeError(
                f"Plugin service '{plugin_id}' does not expose handle_command."
            )
        self._log_info(
            f"Plugin service '{record.service_id}' handling command '{command}'."
        )
        return handle_command(record.context, command, payload or {})

    def get_state(self, plugin_id: str, service_code: str | None = None) -> str | None:
        """Return the current state for a registered service."""
        key = self._resolve_service_key(plugin_id, service_code)
        record = self._records.get(key) if key is not None else None
        return record.state if record else None

    def service_ids(self) -> tuple[str, ...]:
        """Return registered service plugin ids."""
        return tuple(sorted(record.service_id for record in self._records.values()))

    def status(self) -> dict[str, Any]:
        """Return current service manager status."""
        return {
            "registered": len(self._records),
            "dependency_invalid": len(self._dependency_invalid),
            "services": {
                record.service_id: {
                    "plugin_id": record.manifest.plugin_id,
                    "service_code": record.service_runtime.service_code,
                    "policy": record.effective_policy,
                    "state": record.state,
                    "owner_id": self.owner_id,
                    "lease_token": record.lease_token,
                    "restart_count": record.restart_count,
                    "tick_count": record.tick_count,
                    "next_run_seconds": record.next_run_seconds,
                    "last_error": record.last_error,
                    "state_history": tuple(record.state_history),
                }
                for _key, record in sorted(
                    self._records.items(),
                    key=lambda item: item[1].service_id,
                )
            },
            "dependency_invalid_services": tuple(sorted(self._dependency_invalid)),
        }

    def _prepare_record(self, record: _ServiceRecord) -> None:
        plugin_class = self._load_service_class(record)
        instance = self._instantiate_service(plugin_class, record.manifest)
        context = PluginServiceContext(
            plugin_id=record.manifest.plugin_id,
            service_code=record.service_runtime.service_code,
            logger=self._logger,
            stop_event=threading.Event(),
            manifest=record.manifest,
            config_mgr=self._config_mgr,
            plugin_config_manager=PluginConfigManager(
                record.manifest,
                logger=self._logger,
            ),
            _plugin_db_session_factory=self._plugin_db_session_factory,
            _secret_vault=PluginSecretVault(
                plugin_id=record.manifest.plugin_id,
                manifest=record.manifest,
            ),
        )
        self._validate_service_contract(instance, record.manifest, record.service_runtime)
        record.instance = instance
        record.context = context
        record.last_error = None

    def _run_service(self, record: _ServiceRecord) -> None:
        manifest = record.manifest
        service_runtime = record.service_runtime
        if service_runtime is None or record.context is None or record.instance is None:
            self._transition(record, "failed")
            return

        try:
            self._transition(record, "running")
            self._persist_state(record, "running")
            self._log_info(f"Plugin service '{record.service_id}' running.")
            if service_runtime.execution_model == "scheduled":
                self._run_scheduled_service(record)
            else:
                self._run_long_running_service(record)
        except Exception as exc:
            record.last_error = str(exc)
            self._transition(record, "failed")
            self._persist_state(record, "failed", str(exc))
            self._log_exception(f"Plugin service '{record.service_id}' failed", exc)
            self._restart_after_failure(record)
        else:
            if record.context.stop_event.is_set():
                self._transition(record, "stopped")
                self._persist_state(record, "stopped")
                self._release_lease(record)
            elif service_runtime.execution_model == "long_running":
                record.last_error = "Long-running service returned before cancellation."
                self._transition(record, "failed")
                self._persist_state(record, "failed", record.last_error)
                self._restart_after_failure(record)

    def _run_scheduled_service(self, record: _ServiceRecord) -> None:
        service_runtime = record.service_runtime
        schedule = service_runtime.schedule if service_runtime else None
        if schedule is None or record.context is None:
            raise PluginRuntimeError("Scheduled service has no schedule metadata.")

        next_delay = 0.0 if schedule.run_on_start else float(schedule.interval_seconds)
        while not record.context.stop_event.wait(next_delay):
            self._run_tick(record)
            next_delay = self._next_scheduled_delay(schedule)
            record.next_run_seconds = next_delay

    def _run_tick(self, record: _ServiceRecord) -> None:
        schedule = record.service_runtime.schedule
        started = time.monotonic()
        record.instance.tick(record.context)
        record.tick_count += 1
        self._persist_state(record, "running", touch_tick=True)
        if schedule and schedule.timeout_seconds is not None:
            elapsed = time.monotonic() - started
            if elapsed > schedule.timeout_seconds:
                raise PluginRuntimeError(
                    "Scheduled plugin service tick exceeded timeout_seconds. "
                    "Hard cancellation of in-process ticks is not supported."
                )

    @staticmethod
    def _next_scheduled_delay(schedule) -> float:
        jitter = 0.0
        if schedule.jitter_seconds:
            jitter = random.uniform(0, float(schedule.jitter_seconds))
        return float(schedule.interval_seconds) + jitter

    def _run_long_running_service(self, record: _ServiceRecord) -> None:
        record.instance.run(record.context)

    def _restart_after_failure(self, record: _ServiceRecord) -> None:
        service_runtime = record.service_runtime
        if (
            service_runtime is None
            or service_runtime.restart_policy != "on_failure"
            or record.context is None
            or record.context.stop_event.is_set()
            or record.restart_count >= self._max_restart_attempts
        ):
            return

        record.restart_count += 1
        self._log_warning(
            f"Plugin service '{record.service_id}' restarting after failure "
            f"(attempt {record.restart_count})."
        )
        self._transition(record, "starting")
        self._prepare_record(record)
        self._run_service(record)

    @staticmethod
    def _validate_service_contract(
        instance: Any,
        manifest: PluginManifest,
        service_runtime: PluginServiceRuntime,
    ) -> None:
        if service_runtime is None:
            raise PluginRuntimeError(
                f"Plugin '{manifest.plugin_id}' has no service runtime metadata."
            )
        if service_runtime.execution_model == "scheduled" and not hasattr(instance, "tick"):
            raise PluginRuntimeError(
                f"Scheduled service plugin '{manifest.plugin_id}' must expose tick(context)."
            )
        if service_runtime.execution_model == "long_running" and not hasattr(instance, "run"):
            raise PluginRuntimeError(
                f"Long-running service plugin '{manifest.plugin_id}' must expose run(context)."
            )

    def _instantiate_service(self, plugin_class: type, manifest: PluginManifest) -> Any:
        kwargs = {
            "logger": self._logger,
            "config_mgr": self._config_mgr,
            "manifest": manifest,
        }
        try:
            signature = inspect.signature(plugin_class)
        except (TypeError, ValueError):
            signature = None

        if signature is not None:
            kwargs = {
                key: value
                for key, value in kwargs.items()
                if key in signature.parameters
            }
        return plugin_class(**kwargs)

    def _has_missing_database_schema(self, manifest: PluginManifest) -> bool:
        return manifest.database_required and not plugin_schema_payload_path(manifest).is_dir()

    def _load_service_class(self, record: _ServiceRecord) -> type:
        try:
            return self._service_loader(record.manifest, record.service_runtime)
        except TypeError:
            return self._service_loader(record.manifest)

    def _resolve_service_key(
        self,
        plugin_id: str,
        service_code: str | None = None,
    ) -> tuple[str, str] | None:
        if service_code is not None:
            return (plugin_id, service_code)
        default_key = (plugin_id, "default")
        if default_key in self._records:
            return default_key
        matches = [key for key in self._records if key[0] == plugin_id]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise PluginRuntimeError(
                f"Plugin '{plugin_id}' has multiple services; specify service_code."
            )
        return None

    def _start_heartbeat(self, record: _ServiceRecord) -> None:
        if record.context is None or record.lease_token is None:
            return
        thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(record,),
            name=f"orac-plugin-service-heartbeat-{record.service_id}",
            daemon=True,
        )
        record.heartbeat_thread = thread
        thread.start()

    def _heartbeat_loop(self, record: _ServiceRecord) -> None:
        while record.context is not None and not record.context.stop_event.wait(
            self._heartbeat_interval_seconds
        ):
            if record.lease_token is None:
                return
            if not self._lifecycle_store.heartbeat_lease(
                plugin_id=record.manifest.plugin_id,
                service_code=record.service_runtime.service_code,
                owner_id=self.owner_id,
                lease_token=record.lease_token,
                lease_seconds=self._lease_seconds,
            ):
                record.last_error = "Service lease was lost."
                self._transition(record, "lease_lost")
                if record.context is not None:
                    record.context.stop_event.set()
                self._log_error(f"Plugin service '{record.service_id}' lost its lease.")
                return

    def _persist_state(
        self,
        record: _ServiceRecord,
        state: str,
        last_error_message: str | None = None,
        *,
        touch_tick: bool = False,
    ) -> None:
        if record.lease_token is None:
            return
        self._lifecycle_store.mark_state(
            plugin_id=record.manifest.plugin_id,
            service_code=record.service_runtime.service_code,
            owner_id=self.owner_id,
            lease_token=record.lease_token,
            state=state,
            last_error_message=last_error_message,
            touch_tick=touch_tick,
        )

    def _release_lease(self, record: _ServiceRecord) -> None:
        if record.lease_token is None:
            return
        self._lifecycle_store.release_lease(
            plugin_id=record.manifest.plugin_id,
            service_code=record.service_runtime.service_code,
            owner_id=self.owner_id,
            lease_token=record.lease_token,
        )
        record.lease_token = None

    def _transition(self, record: _ServiceRecord, state: str) -> None:
        if state not in PLUGIN_SERVICE_STATES:
            raise ValueError(f"Unknown plugin service state: {state}")
        if record.state == state:
            return
        record.state = state
        record.state_history.append(state)
        self._log_info(
            f"Plugin service '{record.service_id}' transitioned to {state}."
        )

    def _log_debug(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_debug(message)

    def _log_info(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_info(message)

    def _log_warning(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_warning(message)

    def _log_error(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_error(message)

    def _log_exception(self, prefix: str, exc: BaseException) -> None:
        self._log_error(f"{prefix}: {exc}")


def _service_id(plugin_id: str, service_code: str) -> str:
    """Return display id for one plugin service."""
    return plugin_id if service_code == "default" else f"{plugin_id}:{service_code}"


def _default_owner_id() -> str:
    """Return a unique owner id for one service manager instance."""
    hostname = socket.gethostname() or "unknown-host"
    return f"{hostname}:{os.getpid()}:{uuid.uuid4()}"
