"""Tests for managed plugin runtime database sessions."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Verifies ORAC_PLUGIN session creation and restricted database access.

from __future__ import annotations

from pathlib import Path
import sys
import threading
from typing import Any
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_database_session import DEFAULT_PLUGIN_DATABASE_CONNECTION_NAME
from model.plugin_database_session import ORAC_PLUGIN_DATABASE_USER
from model.plugin_database_session import OracPluginDatabaseSession
from model.plugin_database_session import OracPluginDatabaseSessionFactory
from model.plugin_database_session import PluginDatabaseSessionError
from model.plugin_service_manager import PluginServiceContext


class _FakeLogger:
    def __init__(self) -> None:
        self.debug: list[str] = []

    def log_debug(self, message: str) -> None:
        self.debug.append(message)


class _FakeUserSecurity:
    def __init__(
        self,
        *,
        project_identifier: str,
        resource_type: str,
        username: str = ORAC_PLUGIN_DATABASE_USER,
        password: str = "super-secret-password",
        fail: bool = False,
    ) -> None:
        self.project_identifier = project_identifier
        self.resource_type = resource_type
        self.username = username
        self.password = password
        self.fail = fail

    def named_connection_creds(self, connection_name: str) -> tuple[str, str, str]:
        if self.fail:
            raise KeyError(connection_name)
        return self.username, self.password, "orac-test-dsn"

    def connection_property(
        self,
        connection_name: str,
        property_key: str,
        default_value: str | None = None,
    ) -> str | None:
        return default_value


class _FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.description = [("COL1",), ("COL2",)]

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def callproc(self, name: str, parameters: list) -> list:
        self.calls.append(("callproc", name, parameters))
        return parameters

    def callfunc(self, name: str, return_type, parameters: list) -> str:
        self.calls.append(("callfunc", name, return_type, parameters))
        return "RESULT"

    def execute(self, sql: str, bind_vars: dict | None = None) -> None:
        self.calls.append(("execute", sql, bind_vars or {}))

    def fetchall(self) -> list[tuple[str, str]]:
        return [("A", "B")]


class _FakeDBSession:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.user = kwargs["user"]
        self.cursor_obj = _FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class PluginDatabaseSessionTests(unittest.TestCase):
    """Tests the ORAC_PLUGIN database session facade."""

    def test_factory_creates_managed_session_as_orac_plugin(self) -> None:
        logger = _FakeLogger()

        factory = OracPluginDatabaseSessionFactory(
            user_security_factory=lambda **kwargs: _FakeUserSecurity(**kwargs),
            db_session_factory=lambda **kwargs: _FakeDBSession(**kwargs),
            logger=logger,
        )

        session = factory.create()

        self.assertEqual(session.connected_username, ORAC_PLUGIN_DATABASE_USER)
        self.assertTrue(
            any(DEFAULT_PLUGIN_DATABASE_CONNECTION_NAME in message for message in logger.debug)
        )
        self.assertFalse(
            any("super-secret-password" in message for message in logger.debug)
        )

    def test_factory_rejects_core_or_plugin_owner_credentials(self) -> None:
        for username in ("ORAC", "ORAC_CORE", "ORAC_API", "ORAC_CODE", "ORAC_HA", "SYSTEM", "SYS"):
            with self.subTest(username=username):
                factory = OracPluginDatabaseSessionFactory(
                    user_security_factory=(
                        lambda **kwargs: _FakeUserSecurity(username=username, **kwargs)
                    ),
                    db_session_factory=lambda **kwargs: _FakeDBSession(**kwargs),
                )

                with self.assertRaises(PluginDatabaseSessionError):
                    factory.create()

    def test_factory_rejects_arbitrary_database_usernames(self) -> None:
        factory = OracPluginDatabaseSessionFactory(
            user_security_factory=(
                lambda **kwargs: _FakeUserSecurity(username="NELSON_LOPEZ", **kwargs)
            ),
            db_session_factory=lambda **kwargs: _FakeDBSession(**kwargs),
        )

        with self.assertRaisesRegex(PluginDatabaseSessionError, "ORAC_PLUGIN"):
            factory.create()

    def test_service_context_does_not_accept_requested_database_username(self) -> None:
        context = PluginServiceContext(
            plugin_id="home_assistant",
            logger=None,
            stop_event=threading.Event(),
            manifest=None,
            _plugin_db_session_factory=lambda: "managed-session",
        )

        self.assertEqual(context.plugin_db_session(), "managed-session")
        with self.assertRaises(TypeError):
            context.plugin_db_session("SYSTEM")

    def test_missing_orac_plugin_credentials_raise_clear_error_without_secret(self) -> None:
        factory = OracPluginDatabaseSessionFactory(
            user_security_factory=lambda **kwargs: _FakeUserSecurity(fail=True, **kwargs),
            db_session_factory=lambda **kwargs: _FakeDBSession(**kwargs),
        )

        with self.assertRaisesRegex(PluginDatabaseSessionError, "orac-plugin") as caught:
            factory.create()

        self.assertNotIn("super-secret-password", str(caught.exception))

    def test_wrapper_allows_package_calls_and_explicit_commit(self) -> None:
        db_session = _FakeDBSession(
            user=ORAC_PLUGIN_DATABASE_USER,
            password="secret",
            dsn="dsn",
        )
        session = OracPluginDatabaseSession(
            db_session=db_session,
            connected_username=ORAC_PLUGIN_DATABASE_USER,
        )

        result = session.call_procedure(
            "orac_ha.ha_sync_api.merge_area",
            [{"area_id": "kitchen"}],
        )
        function_result = session.call_function(
            "orac_ha.ha_sync_api.begin_sync_run",
            return_type=int,
            parameters=["structural"],
        )
        session.commit()

        self.assertEqual(result, [{"area_id": "kitchen"}])
        self.assertEqual(function_result, "RESULT")
        self.assertTrue(db_session.committed)

    def test_wrapper_rejects_protected_schema_package_calls(self) -> None:
        db_session = _FakeDBSession(
            user=ORAC_PLUGIN_DATABASE_USER,
            password="secret",
            dsn="dsn",
        )
        session = OracPluginDatabaseSession(
            db_session=db_session,
            connected_username=ORAC_PLUGIN_DATABASE_USER,
        )

        with self.assertRaisesRegex(PluginDatabaseSessionError, "protected schema"):
            session.call_procedure("orac_core.some_api.do_work")

    def test_wrapper_rejects_direct_mutating_sql(self) -> None:
        db_session = _FakeDBSession(
            user=ORAC_PLUGIN_DATABASE_USER,
            password="secret",
            dsn="dsn",
        )
        session = OracPluginDatabaseSession(
            db_session=db_session,
            connected_username=ORAC_PLUGIN_DATABASE_USER,
        )

        with self.assertRaisesRegex(PluginDatabaseSessionError, "direct DML"):
            session.call_plsql("begin insert into orac_ha.t values (1); end;")

        with self.assertRaisesRegex(PluginDatabaseSessionError, "SELECT"):
            session.fetch_dicts("delete from orac_ha.t")


if __name__ == "__main__":
    unittest.main()
