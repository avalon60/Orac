"""Tests for plugin installation registry persistence."""
# Author: Clive Bostock
# Date: 12-Jun-2026
# Description: Verifies native Oracle JSON binding for plugin metadata.

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import oracledb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_registry import PluginApexAppRegistryStore
from model.plugin_registry import PluginRegistryError
from model.plugin_registry import PluginRegistryStore
from model.plugin_routing.discovery import PluginDiscovery


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
                "ui_icon_class": None,
                "ui_accent_class": None,
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
        self.assertIsNone(cursor.binds["ui_icon_class"])
        self.assertIsNone(cursor.binds["ui_accent_class"])
        self.assertIn("p_ui_icon_class", cursor.sql)
        self.assertIn("p_ui_accent_class", cursor.sql)
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

    def test_load_enabled_manifest_result_collects_artifact_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            alpha_path = _write_installed_manifest(root, "alpha")
            alpha_manifest = PluginDiscovery(alpha_path).load_manifest(
                alpha_path / "manifest.json",
                plugin_dir=alpha_path / "plugin",
                enforce_filename=False,
            )
            rows = [
                _registry_row(
                    "alpha",
                    installed_path=str(alpha_path),
                    manifest_hash=alpha_manifest.manifest_hash,
                ),
                _registry_row(
                    "drop_box",
                    installed_path=str(
                        root / "var" / "plugins" / "installed" / "drop_box" / "1.0.0"
                    ),
                    manifest_hash="b" * 64,
                ),
            ]
            cursor = _FakeCursor()
            cursor.description = [(column.upper(),) for column in rows[0]]
            cursor.rows = [tuple(row[column] for column in rows[0]) for row in rows]
            session = _FakeSession(cursor)
            store = PluginRegistryStore(session_factory=lambda: session)

            result = store.load_enabled_manifest_result(strict=False)

            self.assertEqual(
                [manifest.plugin_id for manifest in result.manifests],
                ["alpha"],
            )
            self.assertEqual(len(result.issues), 1)
            self.assertEqual(result.issues[0].plugin_id, "drop_box")
            self.assertEqual(result.issues[0].code, "missing_installed_files")

    def test_enabled_manifest_load_remains_strict_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            row = _registry_row(
                "drop_box",
                installed_path=str(
                    root / "var" / "plugins" / "installed" / "drop_box" / "1.0.0"
                ),
                manifest_hash="b" * 64,
            )
            cursor = _FakeCursor()
            cursor.description = [(column.upper(),) for column in row]
            cursor.rows = [tuple(row[column] for column in row)]
            session = _FakeSession(cursor)
            store = PluginRegistryStore(session_factory=lambda: session)

            with self.assertRaisesRegex(
                PluginRegistryError,
                "Registered plugin files are missing",
            ):
                store.enabled_manifests()

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


def _write_installed_manifest(root: Path, plugin_id: str) -> Path:
    """Create a minimal installed plugin artifact fixture."""
    installed_path = root / "var" / "plugins" / "installed" / plugin_id / "1.0.0"
    plugin_dir = installed_path / "plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        "class AlphaPlugin:\n    def execute(self):\n        return None\n",
        encoding="utf-8",
    )
    (installed_path / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "plugin_id": plugin_id,
                "name": "Alpha",
                "description": "Test plugin",
                "version": "1.0.0",
                "enabled": True,
                "capabilities": ["alpha.read"],
                "entitlements": [],
                "entry_point": "plugin:AlphaPlugin",
                "runtime": {"mode": "on_demand"},
            }
        ),
        encoding="utf-8",
    )
    return installed_path


def _registry_row(
    plugin_id: str,
    *,
    installed_path: str,
    manifest_hash: str,
) -> dict[str, str]:
    """Return a runtime-eligible plugin registry row fixture."""
    return {
        "plugin_id": plugin_id,
        "plugin_name": plugin_id.replace("_", " ").title(),
        "plugin_version": "1.0.0",
        "runtime_mode": "on_demand",
        "manifest_hash": manifest_hash,
        "package_hash": "c" * 64,
        "install_source_type": "source",
        "install_source_ref": f"plugins/{plugin_id}",
        "installed_path": installed_path,
        "config_path": "plugin.ini",
        "dependency_fingerprint": "d" * 64,
        "install_status": "success",
        "configuration_status": "not_required",
        "dependency_status": "not_required",
        "database_status": "not_required",
        "readiness_status": "success",
        "enabled": "Y",
        "ui_icon_class": "",
        "ui_accent_class": "",
        "last_error_code": "",
        "last_error_message": "",
        "row_version": "1",
    }


if __name__ == "__main__":
    unittest.main()
