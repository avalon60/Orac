"""Execute canonical Oracle queries in disposable ORAC_PLUGIN sessions."""

# Author: Clive Bostock
# Date: 08-Nov-2026
# Description: Core-only bounded executor, independent of the plugin facade.
# Purpose: Enforce account, deadline, read-only transaction and result bounds.
# Usage: OracleQueryExecutor(session_factory).execute(validated_query).
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import json
import queue
import threading
import time
from typing import Any, Callable

from .models import QueryDenied, ValidatedQuery


def plugin_executor_session(config_mgr: Any) -> Any:
    """Open a dedicated raw driver connection using existing bridge credentials."""
    import oracledb
    from lib.user_security import UserSecurity

    entry = config_mgr.config_value(
        "database", "plugin_dsn_credential_entry", default="orac-plugin"
    )
    project = config_mgr.config_value("global", "project_identifier", default="Orac")
    security = UserSecurity(project_identifier=project, resource_type="dsn")
    username, password, dsn = security.named_connection_creds(connection_name=entry)
    if str(username).upper() != "ORAC_PLUGIN":
        raise QueryDenied("EXECUTOR_IDENTITY")
    # Driver configuration comes from the existing Oracle environment/wallet;
    # no facade or plugin callable ever receives this connection.
    return oracledb.connect(
        user=username, password=password, dsn=dsn, tcp_connect_timeout=5, retry_count=0
    )


def _scalar(value: Any) -> Any:
    """Convert bounded scalar/LOB values into JSON-safe result values."""
    if hasattr(value, "read"):
        value = value.read(1, 1048577)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise QueryDenied("RESULT_TYPE")


class OracleQueryExecutor:
    """Use one disposable connection per query and cancel on overall deadline."""

    def __init__(
        self, session_factory: Callable[[], Any], *, timeout: float = 10.0
    ) -> None:
        """Store the host-owned raw connection factory and deadline."""
        self._factory = session_factory
        self._timeout = min(10.0, timeout)
        self._slots = threading.BoundedSemaphore(2)

    def execute(
        self, query: ValidatedQuery
    ) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...], bool]:
        """Return by the overall deadline even if driver cancellation stalls.

        A stuck driver retains one of two physical slots until its disposable
        session closes. No replacement worker can silently exceed this bound.
        """
        if not self._slots.acquire(blocking=False):
            raise QueryDenied("QUERY_BUSY")
        started = time.monotonic()
        expired = threading.Event()
        holder: list[Any] = []
        responses: queue.Queue = queue.Queue(maxsize=1)

        def run() -> None:
            try:
                responses.put((True, self._execute(query, started, expired, holder)))
            except BaseException as exc:
                responses.put((False, exc))
            finally:
                self._slots.release()

        threading.Thread(target=run, daemon=True, name="orac-query-execution").start()
        try:
            success, result = responses.get(
                timeout=max(0.001, self._timeout - (time.monotonic() - started))
            )
        except queue.Empty:
            expired.set()

            def cancel() -> None:
                if holder:
                    try:
                        holder[0].cancel()
                    except Exception:
                        pass

            threading.Thread(
                target=cancel, daemon=True, name="orac-query-cancel"
            ).start()
            raise QueryDenied("QUERY_TIMEOUT") from None
        if not success:
            if isinstance(result, QueryDenied):
                raise result
            raise QueryDenied("QUERY_FAILED") from None
        return result

    def _execute(
        self,
        query: ValidatedQuery,
        started: float,
        expired: threading.Event,
        holder: list[Any],
    ) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...], bool]:
        """Own the driver session through rollback/close, including late returns."""
        connection = self._factory()
        holder.append(connection)
        try:
            if expired.is_set():
                raise QueryDenied("QUERY_TIMEOUT")
            connection.call_timeout = max(1, int(self._timeout * 1000))
            with connection.cursor() as cursor:
                cursor.execute(
                    "select sys_context('userenv', 'session_user') from dual"
                )
                if str(cursor.fetchone()[0]).upper() != "ORAC_PLUGIN":
                    raise QueryDenied("EXECUTOR_IDENTITY")
                # Establish a fresh transaction after identity verification.
                connection.rollback()
                cursor.execute("set transaction read only")
                cursor.arraysize = 32
                cursor.execute(query.sql, dict(query.binds))
                columns = tuple(str(item[0]) for item in cursor.description)
                rows: list[tuple[Any, ...]] = []
                size = len(json.dumps(columns).encode())
                truncated = False
                while True:
                    if expired.is_set() or time.monotonic() - started >= self._timeout:
                        raise QueryDenied("QUERY_TIMEOUT")
                    row = cursor.fetchone()
                    if row is None:
                        break
                    if len(rows) >= 500:
                        truncated = True
                        break
                    values = tuple(_scalar(value) for value in row)
                    row_size = len(
                        json.dumps(values, ensure_ascii=False, allow_nan=False).encode()
                    )
                    if size + row_size > 1048576 - 65536:
                        truncated = True
                        break
                    rows.append(values)
                    size += row_size
                if expired.is_set():
                    raise QueryDenied("QUERY_TIMEOUT")
                return columns, tuple(rows), truncated
        except QueryDenied:
            raise
        except Exception:
            raise QueryDenied(
                "QUERY_TIMEOUT" if expired.is_set() else "QUERY_FAILED"
            ) from None
        finally:
            try:
                connection.rollback()
            except Exception:
                pass
            # No pooling: cancellation/rollback uncertainty must never leak a
            # session into another user's request.
            try:
                connection.close()
            except Exception:
                pass
