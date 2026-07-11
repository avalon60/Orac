"""Tests for the Orac plugin command-line interface."""

# Author: Clive Bostock
# Date: 28-Jun-2026
# Description: Verifies narrow foreground service-runner command behaviour.

from __future__ import annotations

import contextlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_orac_plugin_module():
    spec = importlib.util.spec_from_file_location(
        "orac_plugin_cli",
        PROJECT_ROOT / "src" / "controller" / "orac-plugin.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Registry:
    def __init__(self, manifests):
        self._manifests = manifests

    def enabled_manifests(self):
        return list(self._manifests)


class _LifecycleStore:
    def __init__(self) -> None:
        self.policy_updates: list[tuple[str, str, str]] = []

    def list_services(self):
        return [
            SimpleNamespace(
                service_id="drop_box:scanner",
                plugin_id="drop_box",
                service_code="scanner",
                effective_policy="manual",
                current_state="registered",
                owner_id="owner",
                lease_token="token",
                lease_expires_on="2026-07-02T12:01:00",
                last_started_on="2026-07-02T12:00:00",
                last_heartbeat_on="2026-07-02T12:00:30",
                last_tick_on="2026-07-02T12:00:40",
                last_error_message=None,
                row_version=1,
            )
        ]

    def get_service(self, plugin_id, service_code):
        return self.list_services()[0]

    def set_service_policy(self, *, plugin_id, service_code, policy):
        self.policy_updates.append((plugin_id, service_code, policy))
        row = self.get_service(plugin_id, service_code)
        row.effective_policy = policy
        row.row_version = 2
        return row


class _ServiceManager:
    def __init__(self) -> None:
        self.registered = []
        self.started: list[tuple[str, str | None]] = []
        self.stopped: list[tuple[str, str | None]] = []
        self._state = "discovered"
        self._service_ids: tuple[str, ...] | None = None

    def register_manifests(self, manifests):
        self.registered = list(manifests)
        return self.status()

    def service_ids(self):
        if self._service_ids is not None:
            return self._service_ids
        return tuple(manifest.plugin_id for manifest in self.registered)

    def start(self, plugin_id, service_code=None):
        self.started.append((plugin_id, service_code))
        self._state = "running"
        return True

    def stop(self, plugin_id, service_code=None):
        self.stopped.append((plugin_id, service_code))
        self._state = "stopped"
        return True

    def status(self):
        return {
            "registered": len(self.registered),
            "services": {
                service_id: {
                    "plugin_id": manifest.plugin_id,
                    "service_code": (
                        service_id.split(":", 1)[1] if ":" in service_id else "default"
                    ),
                    "policy": "manual",
                    "state": self._state,
                    "tick_count": 1,
                    "last_error": None,
                }
                for manifest in self.registered
                for service_id in self.service_ids()
                if service_id == manifest.plugin_id
                or service_id.startswith(f"{manifest.plugin_id}:")
            },
        }


class OracPluginCliTests(unittest.TestCase):
    """Verify foreground plugin service command semantics."""

    @classmethod
    def setUpClass(cls) -> None:
        """Load the hyphenated CLI module once for this test class."""
        cls.cli = _load_orac_plugin_module()

    def test_parser_supports_service_run_duration_without_changing_status(self) -> None:
        parser = self.cli.build_parser()

        service_args = parser.parse_args(
            ["service", "run", "drop_box", "--duration-seconds", "90"]
        )
        status_args = parser.parse_args(["status", "drop_box"])

        self.assertEqual(service_args.command, "service")
        self.assertEqual(service_args.service_command, "run")
        self.assertEqual(service_args.plugin_id, "drop_box")
        self.assertIsNone(service_args.service_code)
        self.assertEqual(service_args.duration_seconds, 90)
        self.assertEqual(status_args.command, "status")
        self.assertEqual(status_args.plugin_id, "drop_box")

    def test_parser_supports_service_status_surface(self) -> None:
        parser = self.cli.build_parser()

        args = parser.parse_args(["service", "status", "drop_box", "scanner"])

        self.assertEqual(args.command, "service")
        self.assertEqual(args.service_command, "status")
        self.assertEqual(args.plugin_id, "drop_box")
        self.assertEqual(args.service_code, "scanner")

    def test_parser_supports_service_policy_surface(self) -> None:
        parser = self.cli.build_parser()

        args = parser.parse_args(["service", "policy", "drop_box", "scanner", "auto"])

        self.assertEqual(args.command, "service")
        self.assertEqual(args.service_command, "policy")
        self.assertEqual(args.plugin_id, "drop_box")
        self.assertEqual(args.service_code, "scanner")
        self.assertEqual(args.policy, "auto")

    def test_parser_rejects_invalid_service_policy(self) -> None:
        parser = self.cli.build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["service", "policy", "drop_box", "scanner", "always"])

    def test_parser_supports_plugin_inventory_list_json(self) -> None:
        parser = self.cli.build_parser()

        args = parser.parse_args(["list", "--json"])

        self.assertEqual(args.command, "list")
        self.assertTrue(args.json)

    def test_plugin_inventory_table_marks_installed_and_unpacked(self) -> None:
        table = self.cli._format_plugin_inventory(
            [
                {
                    "plugin_id": "alpha",
                    "name": "Alpha",
                    "installed": True,
                    "unpacked": True,
                    "installed_version": "1.0.0",
                    "unpacked_version": "1.0.0",
                    "enabled": True,
                    "install_status": "success",
                    "readiness_status": "success",
                    "error": None,
                },
                {
                    "plugin_id": "beta",
                    "name": "Beta",
                    "installed": False,
                    "unpacked": True,
                    "installed_version": None,
                    "unpacked_version": "1.0.0",
                    "enabled": True,
                    "install_status": "not_installed",
                    "readiness_status": None,
                    "error": None,
                },
            ]
        )

        self.assertIn("PLUGIN", table)
        self.assertIn("alpha", table)
        self.assertIn("beta", table)
        self.assertIn("not_installed", table)

    def test_service_status_surface_includes_lease_and_timestamps(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            status = self.cli.show_plugin_service_status(
                lifecycle_store=_LifecycleStore(),
            )

        self.assertEqual(status, 0)
        payload = output.getvalue()
        for token in (
            "drop_box:scanner",
            "effective_policy",
            "current_state",
            "owner_id",
            "lease_token",
            "lease_expires_on",
            "last_started_on",
            "last_heartbeat_on",
            "last_tick_on",
            "last_error_message",
        ):
            self.assertIn(token, payload)

    def test_service_policy_updates_hide_row_version_input(self) -> None:
        output = io.StringIO()
        store = _LifecycleStore()

        with contextlib.redirect_stdout(output):
            status = self.cli.set_plugin_service_policy(
                plugin_id="drop_box",
                service_code="scanner",
                policy="auto",
                lifecycle_store=store,
            )

        self.assertEqual(status, 0)
        self.assertEqual(store.policy_updates, [("drop_box", "scanner", "auto")])
        payload = output.getvalue()
        self.assertIn('"effective_policy": "auto"', payload)
        self.assertIn('"row_version": 2', payload)

    def test_service_policy_function_rejects_invalid_policy(self) -> None:
        with self.assertRaisesRegex(ValueError, "policy must be one of"):
            self.cli.set_plugin_service_policy(
                plugin_id="drop_box",
                service_code="scanner",
                policy="always",
                lifecycle_store=_LifecycleStore(),
            )

    def test_service_run_starts_only_named_foreground_service(self) -> None:
        manifest = SimpleNamespace(plugin_id="drop_box", runtime_mode="service")
        other_manifest = SimpleNamespace(
            plugin_id="home_assistant", runtime_mode="service"
        )
        service_manager = _ServiceManager()

        status = self.cli.run_plugin_service(
            "drop_box",
            duration_seconds=0.01,
            registry_store=_Registry([manifest, other_manifest]),
            service_manager=service_manager,
        )

        self.assertEqual(status, 0)
        self.assertEqual(service_manager.registered, [manifest])
        self.assertEqual(service_manager.started, [("drop_box", "default")])
        self.assertEqual(service_manager.stopped, [("drop_box", "default")])

    def test_service_run_maps_drop_box_alias_to_scanner_service(self) -> None:
        manifest = SimpleNamespace(plugin_id="drop_box", runtime_mode="service")
        service_manager = _ServiceManager()
        service_manager._service_ids = ("drop_box:scanner",)

        status = self.cli.run_plugin_service(
            "drop_box",
            duration_seconds=0.01,
            registry_store=_Registry([manifest]),
            service_manager=service_manager,
        )

        self.assertEqual(status, 0)
        self.assertEqual(service_manager.started, [("drop_box", "scanner")])
        self.assertEqual(service_manager.stopped, [("drop_box", "scanner")])

    def test_service_run_rejects_non_positive_duration(self) -> None:
        with self.assertRaisesRegex(ValueError, "duration-seconds"):
            self.cli.run_plugin_service(
                "drop_box",
                duration_seconds=0,
                registry_store=_Registry([]),
                service_manager=_ServiceManager(),
            )


if __name__ == "__main__":
    unittest.main()
