"""Tests for plugin installation registry persistence."""
# Author: Clive Bostock
# Date: 12-Jun-2026
# Description: Verifies native Oracle JSON binding for plugin metadata.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

import oracledb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_registry import PluginApexAppRegistryStore
from model.plugin_registry import PluginRegistryError
from model.plugin_registry import PluginRegistryStore


class _FakeCursor:
    def __init__(self) -> None:
        self.input_sizes: dict = {}
        self.sql = ""
        self.binds: dict = {}
        self.description = []
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def setinputsizes(self, **kwargs) -> None:
        self.input_sizes = kwargs

    def execute(self, sql: str, binds: dict) -> None:
        self.sql = sql
        self.binds = binds

    def fetchall(self):
        return list(self.rows)


class _FakeSession:
    def __init__(self, cursor: _FakeCursor) -> None:
        self.cursor_obj = cursor
        self.committed = False
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


class PluginRegistryTests(unittest.TestCase):
    """Tests the controlled plugin registry adapter."""

    def test_record_uses_native_json_binds(self) -> None:
        cursor = _FakeCursor()
        session = _FakeSession(cursor)
        store = PluginRegistryStore(session_factory=lambda: session)

        store.record(
            {
                "plugin_id": "home_assistant",
                "plugin_name": "Home Assistant",
                "plugin_version": "1.0.0",
                "runtime_mode": "hybrid",
                "manifest_hash": "a" * 64,
                "package_hash": "b" * 64,
                "install_source_type": "source",
                "install_source_ref": "plugins/home_assistant",
                "installed_path": "var/plugins/installed/home_assistant/1.0.0",
                "config_path": "plugin.ini",
                "capabilities_summary": '["home_assistant.device_control"]',
                "entitlements_summary": '["network.local_http"]',
                "database_schemas_summary": '["orac_ha"]',
                "dependency_declarations": '["requests<3,>=2.32"]',
                "dependency_fingerprint": "c" * 64,
                "install_status": "success",
                "configuration_status": "success",
                "dependency_status": "success",
                "database_status": "deployed",
                "readiness_status": "success",
                "enabled": True,
            }
        )

        self.assertEqual(
            cursor.input_sizes["capabilities_summary"],
            oracledb.DB_TYPE_JSON,
        )
        self.assertEqual(
            cursor.binds["capabilities_summary"],
            ["home_assistant.device_control"],
        )
        self.assertEqual(
            cursor.binds["dependency_declarations"],
            ["requests<3,>=2.32"],
        )
        self.assertNotIn("json(:capabilities_summary)", cursor.sql)
        self.assertTrue(session.committed)
        self.assertTrue(session.closed)

    def test_apex_app_record_uses_native_json_binds(self) -> None:
        cursor = _FakeCursor()
        session = _FakeSession(cursor)
        store = PluginApexAppRegistryStore(session_factory=lambda: session)

        store.record(
            {
                "plugin_id": "home_assistant",
                "plugin_version": "1.0.0",
                "app_alias": "ORAC_HA_STATUS",
                "workspace": "ORAC",
                "parsing_schema": "ORAC_APX_PUB",
                "app_export": "apex/home_assistant_status.sql",
                "declared_application_id": 1043,
                "installed_app_id": 2043,
                "entry_page_id": 1,
                "label": "Home Assistant Status",
                "description": "Plugin status app",
                "required_roles": '["ORAC_ADMIN"]',
                "icon": "fa-home",
                "card_title": "Home Assistant",
                "card_subtitle": "Sync status",
                "install_status": "installed",
                "install_log": "ORAC_PLUGIN_APEX_APP_ID=2043",
                "enabled": True,
            }
        )

        self.assertEqual(cursor.input_sizes["required_roles"], oracledb.DB_TYPE_JSON)
        self.assertEqual(cursor.binds["required_roles"], ["ORAC_ADMIN"])
        self.assertEqual(cursor.binds["app_alias"], "ORAC_HA_STATUS")
        self.assertEqual(cursor.binds["enabled"], "Y")
        self.assertIn("plugin_apex_app_registry_api.upsert_app", cursor.sql)
        self.assertTrue(session.committed)
        self.assertTrue(session.closed)

    def test_list_all_uses_registry_view_without_eligibility_filters(self) -> None:
        cursor = _FakeCursor()
        cursor.description = [("PLUGIN_ID",), ("INSTALL_STATUS",)]
        cursor.rows = [("alpha", "success"), ("beta", "configuration_failed")]
        session = _FakeSession(cursor)
        store = PluginRegistryStore(session_factory=lambda: session)

        rows = store.list_all()

        self.assertEqual(
            rows,
            [
                {"plugin_id": "alpha", "install_status": "success"},
                {"plugin_id": "beta", "install_status": "configuration_failed"},
            ],
        )
        self.assertIn("orac_code.plugin_registry_v", cursor.sql)
        self.assertIn("order by plugin_id", cursor.sql)
        self.assertNotIn("where enabled", cursor.sql.lower())

    def test_list_all_wraps_connection_errors(self) -> None:
        store = PluginRegistryStore(
            session_factory=lambda: (_ for _ in ()).throw(RuntimeError("offline"))
        )

        with self.assertRaisesRegex(PluginRegistryError, "Unable to read"):
            store.list_all()

    def test_apex_app_listing_uses_menu_view(self) -> None:
        cursor = _FakeCursor()
        cursor.description = [("PLUGIN_ID",), ("APP_ALIAS",), ("LABEL",)]
        cursor.rows = [("home_assistant", "ORAC_HA_STATUS", "Home Assistant Status")]
        session = _FakeSession(cursor)
        store = PluginApexAppRegistryStore(session_factory=lambda: session)

        rows = store.list_enabled()

        self.assertEqual(
            rows,
            [
                {
                    "plugin_id": "home_assistant",
                    "app_alias": "ORAC_HA_STATUS",
                    "label": "Home Assistant Status",
                }
            ],
        )
        self.assertIn("orac_code.plugin_apex_app_menu_v", cursor.sql)


if __name__ == "__main__":
    unittest.main()
