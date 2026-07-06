"""Database-backed lifecycle access for Orac-managed plugin services."""
# Author: Clive Bostock
# Date: 02-Jul-2026
# Description: Calls ORAC_CODE service lifecycle APIs for plugin service managers.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from model.plugin_registry import _close_quietly
from model.plugin_registry import _default_session

__author__ = "Clive Bostock"
__date__ = "02-Jul-2026"
__description__ = "Calls ORAC_CODE service lifecycle APIs for plugin service managers."


class PluginServiceLifecycleError(RuntimeError):
    """Raised when plugin service lifecycle state cannot be persisted safely."""


@dataclass(frozen=True)
class PluginServiceStatus:
    """One service lifecycle row returned from ORAC_CODE."""

    plugin_id: str
    service_code: str
    service_id: str
    effective_policy: str
    current_state: str
    owner_id: str | None = None
    lease_token: str | None = None
    lease_expires_on: Any | None = None
    lease_active_yn: str = "N"
    last_started_on: Any | None = None
    last_heartbeat_on: Any | None = None
    last_tick_on: Any | None = None
    last_error_message: str | None = None
    row_version: int | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "PluginServiceStatus":
        """Create status from an Oracle row dictionary."""
        return cls(
            plugin_id=str(row["plugin_id"]),
            service_code=str(row["service_code"]),
            service_id=str(row["service_id"]),
            effective_policy=str(row["effective_policy"]),
            current_state=str(row["current_state"]),
            owner_id=row.get("owner_id"),
            lease_token=row.get("lease_token"),
            lease_expires_on=row.get("lease_expires_on"),
            lease_active_yn=str(row.get("lease_active_yn") or "N"),
            last_started_on=row.get("last_started_on"),
            last_heartbeat_on=row.get("last_heartbeat_on"),
            last_tick_on=row.get("last_tick_on"),
            last_error_message=row.get("last_error_message"),
            row_version=(
                int(row["row_version"]) if row.get("row_version") is not None else None
            ),
        )


class PluginServiceLifecycleStore:
    """Read and update plugin service lifecycle through ORAC_CODE APIs."""

    _PACKAGE = "orac_code.plugin_service_api"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        """Initialise the lifecycle store with an optional session factory."""
        self._session_factory = session_factory or _default_session

    def register_service(
        self,
        *,
        plugin_id: str,
        service_code: str,
        service_name: str | None,
        entry_point: str,
        execution_model: str,
        manifest_policy: str,
    ) -> PluginServiceStatus:
        """Register or refresh one service descriptor and return current status."""
        session = self._connect()
        try:
            with session.cursor() as cursor:
                cursor.callproc(
                    f"{self._PACKAGE}.register_service",
                    [
                        plugin_id,
                        service_code,
                        service_name,
                        entry_point,
                        execution_model,
                        manifest_policy,
                    ],
                )
            session.commit()
            return self.get_service(plugin_id, service_code)
        except Exception as exc:
            raise PluginServiceLifecycleError(
                f"Unable to register plugin service {plugin_id}:{service_code}: {exc}"
            ) from exc
        finally:
            _close_quietly(session)

    def try_acquire_lease(
        self,
        *,
        plugin_id: str,
        service_code: str,
        owner_id: str,
        lease_seconds: int,
    ) -> str | None:
        """Atomically acquire a service lease and return its token when successful."""
        session = self._connect()
        try:
            with session.cursor() as cursor:
                token = cursor.callfunc(
                    f"{self._PACKAGE}.try_acquire_service_lease",
                    str,
                    [plugin_id, service_code, owner_id, lease_seconds],
                )
            session.commit()
            return str(token) if token else None
        except Exception as exc:
            raise PluginServiceLifecycleError(
                f"Unable to acquire plugin service lease {plugin_id}:{service_code}: {exc}"
            ) from exc
        finally:
            _close_quietly(session)

    def heartbeat_lease(
        self,
        *,
        plugin_id: str,
        service_code: str,
        owner_id: str,
        lease_token: str,
        lease_seconds: int,
    ) -> bool:
        """Refresh an active lease using database time."""
        return self._call_number_function(
            "heartbeat_service_lease",
            [plugin_id, service_code, owner_id, lease_token, lease_seconds],
        ) == 1

    def release_lease(
        self,
        *,
        plugin_id: str,
        service_code: str,
        owner_id: str,
        lease_token: str,
    ) -> bool:
        """Release an active lease."""
        return self._call_number_function(
            "release_service_lease",
            [plugin_id, service_code, owner_id, lease_token],
        ) == 1

    def mark_state(
        self,
        *,
        plugin_id: str,
        service_code: str,
        owner_id: str,
        lease_token: str,
        state: str,
        last_error_message: str | None = None,
        touch_tick: bool = False,
    ) -> bool:
        """Persist a lifecycle state for the current lease owner."""
        return self._call_number_function(
            "mark_service_state",
            [
                plugin_id,
                service_code,
                owner_id,
                lease_token,
                state,
                last_error_message,
                "Y" if touch_tick else "N",
            ],
        ) == 1

    def get_service(self, plugin_id: str, service_code: str) -> PluginServiceStatus:
        """Return current lifecycle status for one service."""
        rows = self._query(
            """
            select plugin_id,
                   service_code,
                   service_id,
                   effective_policy,
                   current_state,
                   owner_id,
                   lease_token,
                   lease_expires_on,
                   lease_active_yn,
                   last_started_on,
                   last_heartbeat_on,
                   last_tick_on,
                   last_error_message,
                   row_version
              from orac_code.plugin_service_status_v
             where plugin_id = :plugin_id
               and service_code = :service_code
            """,
            {"plugin_id": plugin_id, "service_code": service_code},
        )
        if not rows:
            raise PluginServiceLifecycleError(
                f"Plugin service is not registered: {plugin_id}:{service_code}"
            )
        return PluginServiceStatus.from_row(rows[0])

    def list_services(self) -> list[PluginServiceStatus]:
        """Return current lifecycle status for all registered services."""
        return [
            PluginServiceStatus.from_row(row)
            for row in self._query(
                """
                select plugin_id,
                       service_code,
                       service_id,
                       effective_policy,
                       current_state,
                       owner_id,
                       lease_token,
                       lease_expires_on,
                       lease_active_yn,
                       last_started_on,
                       last_heartbeat_on,
                       last_tick_on,
                       last_error_message,
                       row_version
                  from orac_code.plugin_service_status_v
                 order by plugin_id, service_code
                """,
                {},
            )
        ]

    def _call_number_function(self, function_name: str, parameters: list[Any]) -> int:
        session = self._connect()
        try:
            with session.cursor() as cursor:
                result = cursor.callfunc(f"{self._PACKAGE}.{function_name}", int, parameters)
            session.commit()
            return int(result or 0)
        except Exception as exc:
            raise PluginServiceLifecycleError(
                f"Unable to call plugin service lifecycle function {function_name}: {exc}"
            ) from exc
        finally:
            _close_quietly(session)

    def _query(self, sql: str, binds: dict[str, Any]) -> list[dict[str, Any]]:
        session = self._connect()
        try:
            with session.cursor() as cursor:
                cursor.execute(sql, binds)
                rows = cursor.fetchall()
                columns = [description[0].lower() for description in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in rows]
        except Exception as exc:
            raise PluginServiceLifecycleError(
                f"Unable to read plugin service lifecycle status: {exc}"
            ) from exc
        finally:
            _close_quietly(session)

    def _connect(self) -> Any:
        """Return an Orac runtime database session."""
        return self._session_factory()
