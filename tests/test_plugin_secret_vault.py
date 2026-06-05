"""Tests for encrypted plugin personal access token vaults."""
# Author: Clive Bostock
# Date: 05-Jun-2026
# Description: Verifies plugin-scoped PAT vault storage, CLI behaviour and runtime boundaries.

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_runtime import PluginRuntimeContext
from model.plugin_secret_vault import DEFAULT_PAT_KEY
from model.plugin_secret_vault import PluginPatVaultStore
from model.plugin_secret_vault import PluginSecretVault
from model.plugin_secret_vault import PluginSecretVaultError
from model.plugin_service_manager import PluginServiceContext


PLUGIN_PAT_MGR_PATH = PROJECT_ROOT / "src" / "controller" / "plugin-pat-mgr.py"


def _load_cli_module():
    """Load the CLI module from its hyphenated script path."""
    spec = importlib.util.spec_from_file_location("plugin_pat_mgr", PLUGIN_PAT_MGR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {PLUGIN_PAT_MGR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime() -> dict:
    """Return a minimal on-demand runtime manifest block."""
    return {"mode": "on_demand"}


def _manifest(plugin_id: str, *, secrets: dict | None = None) -> dict:
    """Return a minimal plugin manifest."""
    manifest = {
        "schema_version": 2,
        "plugin_id": plugin_id,
        "name": plugin_id.title(),
        "description": "Test plugin.",
        "version": "1.0.0",
        "enabled": True,
        "capabilities": [f"{plugin_id}.query"],
        "entitlements": [],
        "entry_point": "plugin:TestPlugin",
        "runtime": _runtime(),
    }
    if secrets is not None:
        manifest["secrets"] = secrets
    return manifest


def _write_plugin(plugins_dir: Path, plugin_id: str, *, secrets: dict | None = None) -> None:
    """Write a minimal discoverable plugin."""
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir()
    (plugin_dir / "plugin.py").write_text("class TestPlugin:\n    pass\n", encoding="utf-8")
    (plugins_dir / f"{plugin_id}.json").write_text(
        json.dumps(_manifest(plugin_id, secrets=secrets)),
        encoding="utf-8",
    )


def _secrets_block(*, allow_custom_keys: bool = False, default_key: str = "access_token") -> dict:
    """Return a standard test secrets block."""
    return {
        "vault": "pat_vault",
        "default_key": default_key,
        "allow_custom_keys": allow_custom_keys,
        "keys": {
            "access_token": {
                "required": True,
                "description": "Test access token.",
                "setup_hint": "Create a test token.",
                "rotation_supported": True,
            },
            "refresh_token": {
                "required": False,
                "description": "Optional refresh token.",
                "setup_hint": "Create a refresh token.",
                "rotation_supported": True,
            },
        },
    }


class PluginSecretVaultTests(unittest.TestCase):
    """Tests encrypted plugin PAT vault storage and scoped access."""

    def test_creates_vault_file_and_round_trips_encrypted_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / ".Orac" / "pat_vault.ini"
            store = PluginPatVaultStore(
                vault_path=vault_path,
                allowed_plugins=("home_assistant",),
            )

            store.set_secret("home_assistant", DEFAULT_PAT_KEY, "plain-token")

            self.assertTrue(vault_path.exists())
            self.assertEqual(store.get_secret("home_assistant"), "plain-token")
            self.assertNotIn("plain-token", vault_path.read_text(encoding="utf-8"))

    def test_updates_multiple_keys_and_lists_without_exposing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir) / "pat_vault.ini"
            store = PluginPatVaultStore(
                vault_path=vault_path,
                allowed_plugins=("home_assistant", "weather"),
            )

            store.set_secret("home_assistant", "access_token", "token-one")
            store.set_secret("home_assistant", "websocket_token", "token-two")
            store.set_secret("home_assistant", "access_token", "token-three")

            self.assertEqual(store.get_secret("home_assistant"), "token-three")
            self.assertEqual(store.list_plugins(), ("home_assistant",))
            self.assertEqual(store.list_keys("home_assistant"), ("access_token", "websocket_token"))
            vault_text = vault_path.read_text(encoding="utf-8")
            self.assertNotIn("token-one", vault_text)
            self.assertNotIn("token-two", vault_text)
            self.assertNotIn("token-three", vault_text)

    def test_delete_key_and_plugin_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = PluginPatVaultStore(
                vault_path=Path(temp_dir) / "pat_vault.ini",
                allowed_plugins=("home_assistant",),
            )
            store.set_secret("home_assistant", "access_token", "token")
            store.set_secret("home_assistant", "refresh_token", "refresh")

            self.assertTrue(store.delete_key("home_assistant", "refresh_token"))
            self.assertEqual(store.list_keys("home_assistant"), ("access_token",))
            self.assertTrue(store.delete_plugin("home_assistant"))
            self.assertEqual(store.list_plugins(), ())

    def test_rejects_unknown_plugin_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = PluginPatVaultStore(
                vault_path=Path(temp_dir) / "pat_vault.ini",
                allowed_plugins=("home_assistant",),
            )

            with self.assertRaisesRegex(PluginSecretVaultError, "Unknown plugin"):
                store.set_secret("weather", "access_token", "token")

    def test_validates_plugin_names_against_discovered_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir) / "plugins"
            plugins_dir.mkdir()
            _write_plugin(plugins_dir, "home_assistant")
            store = PluginPatVaultStore(
                vault_path=Path(temp_dir) / "pat_vault.ini",
                plugins_dir=plugins_dir,
            )

            store.set_secret("home_assistant", "access_token", "token")

            self.assertEqual(store.get_secret("home_assistant"), "token")
            with self.assertRaisesRegex(PluginSecretVaultError, "Unknown plugin"):
                store.set_secret("missing_plugin", "access_token", "token")

    def test_rejects_undeclared_secret_keys_when_custom_keys_are_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir) / "plugins"
            plugins_dir.mkdir()
            _write_plugin(
                plugins_dir,
                "home_assistant",
                secrets=_secrets_block(allow_custom_keys=False),
            )
            store = PluginPatVaultStore(
                vault_path=Path(temp_dir) / "pat_vault.ini",
                plugins_dir=plugins_dir,
            )

            store.set_secret("home_assistant", "access_token", "token")
            with self.assertRaisesRegex(PluginSecretVaultError, "not declared"):
                store.set_secret("home_assistant", "websocket_token", "token")

    def test_allows_undeclared_secret_keys_when_custom_keys_are_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir) / "plugins"
            plugins_dir.mkdir()
            _write_plugin(
                plugins_dir,
                "home_assistant",
                secrets=_secrets_block(allow_custom_keys=True),
            )
            store = PluginPatVaultStore(
                vault_path=Path(temp_dir) / "pat_vault.ini",
                plugins_dir=plugins_dir,
            )

            store.set_secret("home_assistant", "websocket_token", "token")

            self.assertEqual(store.get_secret("home_assistant", "websocket_token"), "token")

    def test_manifest_default_key_is_used_by_scoped_vault_get(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir) / "plugins"
            plugins_dir.mkdir()
            _write_plugin(
                plugins_dir,
                "home_assistant",
                secrets=_secrets_block(default_key="refresh_token"),
            )
            store = PluginPatVaultStore(
                vault_path=Path(temp_dir) / "pat_vault.ini",
                plugins_dir=plugins_dir,
            )
            store.set_secret("home_assistant", "refresh_token", "refresh")
            store.set_secret("home_assistant", "access_token", "access")
            vault = PluginSecretVault(plugin_id="home_assistant", store=store)

            self.assertEqual(vault.get(), "refresh")
            self.assertEqual(vault.get("access_token"), "access")

    def test_runtime_context_exposes_scoped_vault_only(self) -> None:
        store = PluginPatVaultStore(
            vault_path=Path(tempfile.gettempdir()) / "unused-pat-vault.ini",
            allowed_plugins=("home_assistant", "weather"),
        )
        home_vault = PluginSecretVault(plugin_id="home_assistant", store=store)
        context = PluginRuntimeContext(
            manifest=type("Manifest", (), {"plugin_id": "home_assistant"})(),
            logger=None,
            config_mgr=None,
            auth_user="clive",
            _secret_vault=home_vault,
        )

        self.assertIs(context.secret_vault, home_vault)
        self.assertEqual(context.secret_vault.plugin_id, "home_assistant")
        self.assertFalse(hasattr(context.secret_vault, "get_secret"))

    def test_service_context_exposes_scoped_vault_only(self) -> None:
        store = PluginPatVaultStore(
            vault_path=Path(tempfile.gettempdir()) / "unused-pat-vault.ini",
            allowed_plugins=("home_assistant", "weather"),
        )
        home_vault = PluginSecretVault(plugin_id="home_assistant", store=store)
        context = PluginServiceContext(
            plugin_id="home_assistant",
            logger=None,
            stop_event=threading.Event(),
            manifest=None,
            _secret_vault=home_vault,
        )

        self.assertIs(context.secret_vault, home_vault)
        self.assertEqual(context.secret_vault.plugin_id, "home_assistant")
        self.assertFalse(hasattr(context.secret_vault, "get_secret"))

    def test_cli_set_list_get_and_delete(self) -> None:
        cli = _load_cli_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            plugins_dir = Path(temp_dir) / "plugins"
            plugins_dir.mkdir()
            _write_plugin(
                plugins_dir,
                "home_assistant",
                secrets=_secrets_block(allow_custom_keys=False),
            )
            vault_path = Path(temp_dir) / "pat_vault.ini"

            with patch("getpass.getpass", return_value="secret-token"):
                set_code, set_out, set_err = _run_cli(
                    cli,
                    "--plugin",
                    "home_assistant",
                    "--set",
                    "access_token",
                    "--vault-path",
                    str(vault_path),
                    "--plugins-dir",
                    str(plugins_dir),
                )
            list_code, list_out, _list_err = _run_cli(
                cli,
                "--plugin",
                "home_assistant",
                "--list-keys",
                "--vault-path",
                str(vault_path),
                "--plugins-dir",
                str(plugins_dir),
            )
            expected_code, expected_out, _expected_err = _run_cli(
                cli,
                "--plugin",
                "home_assistant",
                "--list-expected",
                "--vault-path",
                str(vault_path),
                "--plugins-dir",
                str(plugins_dir),
            )
            check_code, check_out, _check_err = _run_cli(
                cli,
                "--plugin",
                "home_assistant",
                "--check",
                "access_token",
                "--vault-path",
                str(vault_path),
                "--plugins-dir",
                str(plugins_dir),
            )
            get_denied_code, _get_denied_out, get_denied_err = _run_cli(
                cli,
                "--plugin",
                "home_assistant",
                "--get",
                "access_token",
                "--vault-path",
                str(vault_path),
                "--plugins-dir",
                str(plugins_dir),
            )
            get_code, get_out, _get_err = _run_cli(
                cli,
                "--plugin",
                "home_assistant",
                "--get",
                "access_token",
                "--reveal",
                "--vault-path",
                str(vault_path),
                "--plugins-dir",
                str(plugins_dir),
            )
            delete_code, delete_out, _delete_err = _run_cli(
                cli,
                "--plugin",
                "home_assistant",
                "--delete-key",
                "access_token",
                "--yes",
                "--vault-path",
                str(vault_path),
                "--plugins-dir",
                str(plugins_dir),
            )

            self.assertEqual(set_code, 0, set_err)
            self.assertIn("Stored encrypted secret", set_out)
            self.assertEqual(list_code, 0)
            self.assertEqual(list_out.strip(), "access_token")
            self.assertEqual(expected_code, 0)
            self.assertIn("access_token\trequired", expected_out)
            self.assertEqual(check_code, 0)
            self.assertIn("is configured", check_out)
            self.assertEqual(get_denied_code, 2)
            self.assertIn("--reveal", get_denied_err)
            self.assertEqual(get_code, 0)
            self.assertEqual(get_out.strip(), "secret-token")
            self.assertEqual(delete_code, 0)
            self.assertIn("Deleted secret", delete_out)
            self.assertNotIn("secret-token", vault_path.read_text(encoding="utf-8"))


def _run_cli(cli, *args: str) -> tuple[int, str, str]:
    """Run the CLI main function and capture text streams."""
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli.main(list(args))
    return code, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
