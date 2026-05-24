"""Orac-owned lifecycle manager for service-capable plugins."""
# Author: Clive Bostock
# Date: 2026-05-20
# Description: Provides supervised service plugin execution without allowing
#   plugins to own unmanaged background loops.

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
from pathlib import Path
import random
import threading
import time
from typing import Any, Callable, Protocol

from lib.fsutils import project_home
from model.plugin_routing.models import PluginManifest
from model.plugin_runtime import PluginRuntimeError, load_plugin_service_class


PLUGIN_SERVICE_STATES = {
    "discovered",
    "starting",
    "running",
    "unhealthy",
    "stopping",
    "stopped",
    "failed",
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
    logger: Any
    stop_event: threading.Event
    manifest: PluginManifest
    config_mgr: Any | None = None


@dataclass
class _ServiceRecord:
    """Internal state for one registered service plugin."""

    manifest: PluginManifest
    state: str = "discovered"
    context: PluginServiceContext | None = None
    instance: Any | None = None
    thread: threading.Thread | None = None
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
        service_loader: Callable[[PluginManifest], type] = load_plugin_service_class,
        max_restart_attempts: int = 1,
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
        self._max_restart_attempts = max_restart_attempts
        self._records: dict[str, _ServiceRecord] = {}
        self._dependency_invalid: dict[str, PluginManifest] = {}

    def register_manifests(self, manifests: list[PluginManifest]) -> dict[str, Any]:
        """Register enabled, dependency-valid service or hybrid manifests."""
        self._records.clear()
        self._dependency_invalid.clear()

        for manifest in manifests:
            if not manifest.enabled or manifest.runtime_mode not in {"service", "hybrid"}:
                continue
            if manifest.service_runtime is None:
                self._log_error(
                    f"Plugin service '{manifest.plugin_id}' skipped because runtime.service is missing."
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
            self._records[manifest.plugin_id] = _ServiceRecord(manifest=manifest)
            self._log_info(f"Plugin service '{manifest.plugin_id}' discovered.")

        return self.status()

    def start_auto_services(self) -> None:
        """Start all registered services whose start policy is auto."""
        for plugin_id, record in list(self._records.items()):
            service_runtime = record.manifest.service_runtime
            if service_runtime and service_runtime.start_policy == "auto":
                self.start(plugin_id)

    def start(self, plugin_id: str) -> bool:
        """Start a registered plugin service."""
        record = self._records.get(plugin_id)
        if record is None:
            self._log_warning(f"Plugin service '{plugin_id}' was not registered.")
            return False
        if record.thread is not None and record.thread.is_alive():
            self._log_debug(f"Plugin service '{plugin_id}' is already running.")
            return True

        self._transition(record, "starting")
        try:
            self._prepare_record(record)
            thread = threading.Thread(
                target=self._run_service,
                args=(record,),
                name=f"orac-plugin-service-{plugin_id}",
                daemon=False,
            )
            record.thread = thread
            thread.start()
            return True
        except Exception as exc:
            record.last_error = str(exc)
            self._transition(record, "failed")
            self._log_exception(f"Plugin service '{plugin_id}' failed to start", exc)
            return False

    def stop(self, plugin_id: str) -> bool:
        """Request cancellation and wait up to the service shutdown timeout."""
        record = self._records.get(plugin_id)
        if record is None:
            self._log_warning(f"Plugin service '{plugin_id}' was not registered.")
            return False

        service_runtime = record.manifest.service_runtime
        timeout_seconds = service_runtime.shutdown_timeout_seconds if service_runtime else 1
        self._transition(record, "stopping")
        if record.context is not None:
            record.context.stop_event.set()
        if record.instance is not None and hasattr(record.instance, "stop"):
            try:
                record.instance.stop(record.context)
            except Exception as exc:
                record.last_error = str(exc)
                self._log_exception(
                    f"Plugin service '{plugin_id}' stop hook failed",
                    exc,
                )

        if record.thread is not None:
            record.thread.join(timeout=timeout_seconds)
            if record.thread.is_alive():
                record.last_error = (
                    f"Service did not stop within {timeout_seconds} seconds."
                )
                self._transition(record, "failed")
                self._log_error(
                    f"Plugin service '{plugin_id}' did not stop within "
                    f"{timeout_seconds} seconds."
                )
                return False

        self._transition(record, "stopped")
        self._log_info(f"Plugin service '{plugin_id}' stopped.")
        return True

    def stop_all(self) -> None:
        """Stop all registered plugin services."""
        for plugin_id in list(self._records):
            self.stop(plugin_id)

    def check_health(self, plugin_id: str) -> bool:
        """Run a plugin service health check when the service exposes one."""
        record = self._records.get(plugin_id)
        if record is None or record.instance is None:
            return False
        if not hasattr(record.instance, "health"):
            return record.state == "running"
        try:
            healthy = bool(record.instance.health(record.context))
        except Exception as exc:
            record.last_error = str(exc)
            self._transition(record, "unhealthy")
            self._log_exception(f"Plugin service '{plugin_id}' health check failed", exc)
            return False
        if healthy:
            if record.state == "unhealthy":
                self._transition(record, "running")
            return True
        self._transition(record, "unhealthy")
        self._log_warning(f"Plugin service '{plugin_id}' reported unhealthy.")
        return False

    def get_state(self, plugin_id: str) -> str | None:
        """Return the current state for a registered service."""
        record = self._records.get(plugin_id)
        return record.state if record else None

    def service_ids(self) -> tuple[str, ...]:
        """Return registered service plugin ids."""
        return tuple(sorted(self._records))

    def status(self) -> dict[str, Any]:
        """Return current service manager status."""
        return {
            "registered": len(self._records),
            "dependency_invalid": len(self._dependency_invalid),
            "services": {
                plugin_id: {
                    "state": record.state,
                    "restart_count": record.restart_count,
                    "tick_count": record.tick_count,
                    "next_run_seconds": record.next_run_seconds,
                    "last_error": record.last_error,
                    "state_history": tuple(record.state_history),
                }
                for plugin_id, record in sorted(self._records.items())
            },
            "dependency_invalid_services": tuple(sorted(self._dependency_invalid)),
        }

    def _prepare_record(self, record: _ServiceRecord) -> None:
        plugin_class = self._service_loader(record.manifest)
        instance = self._instantiate_service(plugin_class, record.manifest)
        context = PluginServiceContext(
            plugin_id=record.manifest.plugin_id,
            logger=self._logger,
            stop_event=threading.Event(),
            manifest=record.manifest,
            config_mgr=self._config_mgr,
        )
        self._validate_service_contract(instance, record.manifest)
        record.instance = instance
        record.context = context
        record.last_error = None

    def _run_service(self, record: _ServiceRecord) -> None:
        manifest = record.manifest
        service_runtime = manifest.service_runtime
        if service_runtime is None or record.context is None or record.instance is None:
            self._transition(record, "failed")
            return

        try:
            self._transition(record, "running")
            self._log_info(f"Plugin service '{manifest.plugin_id}' running.")
            if service_runtime.execution_model == "scheduled":
                self._run_scheduled_service(record)
            else:
                self._run_long_running_service(record)
        except Exception as exc:
            record.last_error = str(exc)
            self._transition(record, "failed")
            self._log_exception(f"Plugin service '{manifest.plugin_id}' failed", exc)
            self._restart_after_failure(record)
        else:
            if record.context.stop_event.is_set():
                self._transition(record, "stopped")
            elif service_runtime.execution_model == "long_running":
                record.last_error = "Long-running service returned before cancellation."
                self._transition(record, "failed")
                self._restart_after_failure(record)

    def _run_scheduled_service(self, record: _ServiceRecord) -> None:
        service_runtime = record.manifest.service_runtime
        schedule = service_runtime.schedule if service_runtime else None
        if schedule is None or record.context is None:
            raise PluginRuntimeError("Scheduled service has no schedule metadata.")

        next_delay = 0.0 if schedule.run_on_start else float(schedule.interval_seconds)
        while not record.context.stop_event.wait(next_delay):
            self._run_tick(record)
            next_delay = self._next_scheduled_delay(schedule)
            record.next_run_seconds = next_delay

    def _run_tick(self, record: _ServiceRecord) -> None:
        schedule = record.manifest.service_runtime.schedule
        started = time.monotonic()
        record.instance.tick(record.context)
        record.tick_count += 1
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
        service_runtime = record.manifest.service_runtime
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
            f"Plugin service '{record.manifest.plugin_id}' restarting after failure "
            f"(attempt {record.restart_count})."
        )
        self._transition(record, "starting")
        self._prepare_record(record)
        self._run_service(record)

    @staticmethod
    def _validate_service_contract(instance: Any, manifest: PluginManifest) -> None:
        service_runtime = manifest.service_runtime
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
        if not manifest.database_required:
            return False
        for schema in manifest.database_schemas:
            if not (self._database_schema_root / schema.schema_name).is_dir():
                return True
        return False

    def _transition(self, record: _ServiceRecord, state: str) -> None:
        if state not in PLUGIN_SERVICE_STATES:
            raise ValueError(f"Unknown plugin service state: {state}")
        if record.state == state:
            return
        record.state = state
        record.state_history.append(state)
        self._log_info(
            f"Plugin service '{record.manifest.plugin_id}' transitioned to {state}."
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
