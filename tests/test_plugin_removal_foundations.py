"""Exercise removal transaction boundaries and single-host maintenance access."""

# Author: Clive Bostock
# Date: 12-Sep-2026
# Description: Tests fail-closed registry mutations and execution exclusion.

from __future__ import annotations

from pathlib import Path
import copy
import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from model.plugin_execution_lock import PluginExecutionLock, PluginMaintenanceError
from model.plugin_registry import PluginRegistryError, PluginRegistryStore
from model.plugin_installer import PluginInstaller, PluginInstallationError
from model.plugin_installer import PluginRemovalConfirmationError
from orac_core.plugin_registry_policy import plugin_registry_row_runtime_eligible


class PluginExecutionLockTests(unittest.TestCase):
    """Maintenance cannot overlap supported runners or another mutation."""

    def test_pat_mutation_cannot_overlap_removal(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "plugin_pat_cli", ROOT / "src/controller/plugin-pat-mgr.py"
        )
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(cli, "PROJECT_ROOT", root),
                patch.object(cli, "PluginPatVaultStore"),
                patch.object(cli, "_run") as run,
                contextlib.redirect_stderr(io.StringIO()),
                PluginExecutionLock(root, exclusive=True),
            ):
                self.assertEqual(cli.main(["--plugin", "alpha", "--set", "token"]), 1)
                run.assert_not_called()

    def test_parent_symlink_cannot_redirect_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root / "external"
            external.mkdir()
            (root / "var").symlink_to(external, target_is_directory=True)
            with self.assertRaises(OSError):
                with PluginExecutionLock(root, exclusive=True):
                    self.fail("Followed lock parent symlink")
            self.assertEqual(list(external.iterdir()), [])

    def test_shared_runners_exclude_maintenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with PluginExecutionLock(root), PluginExecutionLock(root):
                with self.assertRaises(PluginMaintenanceError):
                    with PluginExecutionLock(root, exclusive=True):
                        self.fail("Maintenance overlapped execution")
            with PluginExecutionLock(root, exclusive=True):
                with self.assertRaises(PluginMaintenanceError):
                    with PluginExecutionLock(root):
                        self.fail("Execution overlapped maintenance")

    def test_failure_releases_lock_without_unlinking_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = PluginExecutionLock(root, exclusive=True)
            with self.assertRaisesRegex(ValueError, "interrupted"):
                with lock:
                    inode = lock.path.stat().st_ino
                    raise ValueError("interrupted")
            with PluginExecutionLock(root, exclusive=True) as retry:
                self.assertEqual(inode, retry.path.stat().st_ino)

    def test_symlink_cannot_replace_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = PluginExecutionLock(root)
            lock.path.parent.mkdir(parents=True)
            target = root / "unrelated"
            target.touch()
            lock.path.symlink_to(target)
            with self.assertRaises(OSError):
                with lock:
                    self.fail("Followed lock symlink")


class PluginRemovalRegistryTests(unittest.TestCase):
    """Lifecycle writes must commit together or remain retryable failures."""

    def setUp(self) -> None:
        self.session = MagicMock()
        self.cursor = self.session.cursor.return_value.__enter__.return_value
        self.store = PluginRegistryStore(session_factory=lambda: self.session)

    def test_begin_fences_exact_registration_with_native_inventory(self) -> None:
        inventory = {"schemas": [], "applications": [], "paths": []}
        self.store.begin_removal(
            plugin_id="weather",
            registry_id=17,
            removal_id="a" * 32,
            keep_schema=False,
            database_identity="db:pdb",
            inventory=inventory,
            confirmed_by="operator",
        )
        sql, binds = self.cursor.execute.call_args.args
        self.assertIn("plugin_registry_api.begin_removal", sql)
        self.assertEqual(17, binds["registry_id"])
        self.assertEqual("DROP", binds["disposition"])
        self.assertEqual(inventory, binds["inventory"])
        self.cursor.setinputsizes.assert_called_once()
        self.session.commit.assert_called_once()
        self.session.close.assert_called_once()

    def test_keep_schema_authorization_is_persisted(self) -> None:
        self.store.begin_removal(
            plugin_id="alpha",
            registry_id=17,
            removal_id="b" * 32,
            keep_schema=True,
            database_identity="db:pdb",
            inventory={"schemas": ["ALPHA"]},
            confirmed_by="operator",
        )
        self.assertEqual("KEEP", self.cursor.execute.call_args.args[1]["disposition"])

    def test_invalid_or_unbounded_checkpoints_never_reach_database(self) -> None:
        for checkpoints in ({"text": "x" * 65537}, {"number": float("nan")}, []):
            with self.subTest(checkpoints_type=type(checkpoints).__name__):
                with self.assertRaises(PluginRegistryError):
                    self.store.checkpoint_removal(
                        removal_id="a" * 32,
                        registry_id=17,
                        checkpoints=checkpoints,
                        external_complete=False,
                        files_complete=False,
                    )
        self.session.cursor.assert_not_called()

    def test_finalize_failure_rolls_back_without_exposing_database_error(self) -> None:
        self.cursor.execute.side_effect = RuntimeError("private connection detail")
        with self.assertRaises(PluginRegistryError) as raised:
            self.store.finalize_removal(removal_id="a" * 32, registry_id=17)
        self.assertNotIn("private", str(raised.exception))
        self.session.commit.assert_not_called()
        self.session.rollback.assert_called_once()
        self.session.close.assert_called_once()

    def test_uncertain_commit_is_not_reported_as_success(self) -> None:
        self.session.commit.side_effect = OSError("connection lost")
        with self.assertRaises(PluginRegistryError):
            self.store.finalize_removal(removal_id="a" * 32, registry_id=17)
        self.session.close.assert_called_once()

    def test_enable_uses_controlled_api_not_upsert(self) -> None:
        self.store.set_enabled("weather", enabled=True)
        sql, binds = self.cursor.execute.call_args.args
        self.assertIn("plugin_registry_api.set_enabled", sql)
        self.assertNotIn("upsert", sql)
        self.assertEqual({"plugin_id": "weather", "enabled": "Y"}, binds)

    def test_removal_fence_overrides_otherwise_ready_state(self) -> None:
        row = dict(
            enabled="Y",
            install_status="success",
            configuration_status="success",
            dependency_status="success",
            database_status="not_required",
            readiness_status="success",
        )
        self.assertTrue(plugin_registry_row_runtime_eligible(row))
        row["removal_id"] = "a" * 32
        self.assertFalse(plugin_registry_row_runtime_eligible(row))

    def test_check_refuses_removal_before_readiness_or_status_writes(self) -> None:
        registry = MagicMock()
        registry.get.return_value = {"plugin_id": "weather", "removal_id": "a" * 32}
        checker = MagicMock()
        installer = PluginInstaller(
            registry=registry, command_dependency_checker=checker
        )
        with self.assertRaisesRegex(PluginInstallationError, "incomplete removal"):
            installer.check("weather")
        checker.check.assert_not_called()
        registry.record_command_status.assert_not_called()

    def test_acceptance_is_rollback_only_and_has_no_external_cleanup(self) -> None:
        sql = (
            (ROOT / "resources/db/acceptance/plugin_removal_lifecycle.sql")
            .read_text()
            .lower()
        )
        self.assertIn("whenever sqlerror exit failure rollback", sql)
        self.assertIn("rollback;", sql)
        for forbidden in (
            "commit;",
            "drop user",
            "apex_application_install",
            "execute immediate",
        ):
            self.assertNotIn(forbidden, sql)
        self.assertIn("reinstall adopted historical scope", sql)
        self.assertIn("failed finalisation lost the durable fence", sql)


class PluginApexRemovalBoundaryTests(unittest.TestCase):
    """Exercise administrative APEX boundaries without contacting Oracle."""

    def test_apex_preflight_is_read_only_and_cleanup_requires_the_same_receipt(self):
        from model.plugin_apex_installation import _apex_removal_sql

        manifest = SimpleNamespace(
            plugin_id="alpha",
            apex_apps=[
                SimpleNamespace(
                    alias="ALPHA",
                    workspace="ORAC",
                    parsing_schema="ORAC_APX_PUB",
                    install_required=True,
                )
            ],
        )
        arguments = dict(
            oracle_pdb="FREEPDB1",
            plugin_registry_id=8,
            database_identity="12:AB:FREEPDB1",
            removal_id=None,
        )
        preflight = _apex_removal_sql(manifest, **arguments, remove=False)
        for forbidden in ("remove_application(", "set_application_status(", "commit;"):
            self.assertNotIn(forbidden, preflight)
        cleanup = _apex_removal_sql(
            manifest,
            **{**arguments, "removal_id": "a" * 32},
            remove=True,
        )
        for required in (
            "json_equal(authorized.receipt, l_receipt)",
            "APEX registration or removal fence changed",
            "apex_appl_automations",
            "gv$session",
            "ORAC_INSTALL_RECEIPT",
            "l_expected_id in (1042, 1043, 10042)",
        ):
            self.assertIn(required, cleanup)
        self.assertLess(
            cleanup.index("set_application_status("),
            cleanup.index("remove_application("),
        )
        self.assertLess(
            cleanup.index("from gv$session"), cleanup.index("remove_application(")
        )
        for forbidden in (
            "remove_workspace",
            "drop user",
            "drop workspace",
            "kill session",
        ):
            self.assertNotIn(forbidden, cleanup.lower())

    def test_apex_removal_requires_a_durable_operation(self):
        from model.plugin_apex_installation import (
            _apex_removal_sql,
            PluginApexAppInstallError,
        )

        with self.assertRaises(PluginApexAppInstallError):
            _apex_removal_sql(
                SimpleNamespace(plugin_id="alpha", apex_apps=[]),
                oracle_pdb="FREEPDB1",
                plugin_registry_id=8,
                database_identity="12:AB:FREEPDB1",
                removal_id=None,
                remove=True,
            )


class PluginRemovalOrchestrationTests(unittest.TestCase):
    """Exercise failures around real managed files with mocked external resources."""

    def setUp(self) -> None:
        from model.plugin_routing.models import PluginManifest

        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = self.root / "config/alpha"
        self.installed = self.root / "var/plugins/installed/alpha/1.0"
        self.snapshot = self.root / "var/plugins/snapshots/alpha/hash"
        for directory in (
            self.config,
            self.installed,
            self.snapshot,
            self.root / "plugins/alpha",
        ):
            directory.mkdir(parents=True)
            (directory / "retained.txt").write_text("payload")
        self.row = dict(
            plugin_id="alpha",
            plugin_version="1.0",
            plugin_registry_id=42,
            knowledge_scope_id=43,
            manifest_hash="a" * 64,
            enabled="Y",
            installed_path=str(self.installed),
            config_path=str(self.config / "plugin.ini"),
            removal_id=None,
        )
        self.operations = []
        self.registry = MagicMock()
        self.registry.get.side_effect = lambda _plugin: copy.deepcopy(self.row)
        self.registry.removal_history.side_effect = lambda _plugin: copy.deepcopy(
            self.operations
        )
        self.registry.begin_removal.side_effect = self._begin
        self.registry.checkpoint_removal.side_effect = self._checkpoint
        self.registry.finalize_removal.side_effect = self._finalize
        self.runner = MagicMock()
        self.runner.schema_removal_inventory.return_value = dict(
            plugin_id="alpha",
            plugin_registry_id=42,
            database_identity="db:pdb",
            schemas=[],
        )
        self.database = MagicMock()
        self.database.administrative_runner_for.return_value = self.runner
        self.apex = MagicMock()
        self.apex.removal_inventory.return_value = []
        self.vault = MagicMock()
        self.services = MagicMock()
        self.services.list_services.return_value = []
        self.installer = PluginInstaller(
            project_root=self.root,
            config_root=self.root / "config",
            registry=self.registry,
            database_deployer=self.database,
            apex_app_installer=self.apex,
            service_lifecycle=self.services,
            secret_vault=self.vault,
            audit_adapter=MagicMock(),
        )
        self.manifest = PluginManifest(
            schema_version=2,
            plugin_id="alpha",
            name="Alpha",
            description="Test",
            version="1.0",
            enabled=True,
            capabilities=(),
            entitlements=(),
            entities=(),
            examples=(),
            entry_point=None,
            manifest_path=self.installed / "manifest.json",
            plugin_dir=self.installed / "plugin",
            manifest_hash="a" * 64,
        )
        self.installer._registered_removal_manifest = MagicMock(
            return_value=self.manifest
        )

    def _begin(self, **values):
        self.row.update(removal_id=values["removal_id"], enabled="N")
        self.operations.append(
            dict(
                removal_id=values["removal_id"],
                plugin_registry_id=42,
                schema_disposition="KEEP" if values["keep_schema"] else "DROP",
                resource_inventory=copy.deepcopy(values["inventory"]),
                checkpoints={},
                external_complete_yn="N",
                files_complete_yn="N",
                completed_on=None,
                confirmed_by=values["confirmed_by"],
            )
        )

    def _checkpoint(self, **values):
        self.operations[0].update(
            checkpoints=copy.deepcopy(values["checkpoints"]),
            external_complete_yn="Y" if values["external_complete"] else "N",
            files_complete_yn="Y" if values["files_complete"] else "N",
        )

    def _finalize(self, **_values):
        self.assertEqual(self.operations[0]["external_complete_yn"], "Y")
        self.assertEqual(self.operations[0]["files_complete_yn"], "Y")
        self.assertFalse(self.config.exists())
        self.assertFalse(self.installed.exists())
        self.assertFalse(self.snapshot.exists())
        self.operations[0]["completed_on"] = "test completion"
        self.row = None

    def _remove(self, **kwargs):
        return self.installer.remove(
            "alpha", confirmed_by="operator", confirm=lambda _: True, **kwargs
        )

    def test_dry_run_and_declined_confirmation_never_fence_or_clean(self) -> None:
        result = self.installer.remove("alpha", dry_run=True)
        self.assertEqual(result.status, "dry_run")
        with self.assertRaises(PluginRemovalConfirmationError):
            self.installer.remove("alpha")
        self.registry.begin_removal.assert_not_called()
        self.apex.remove.assert_not_called()
        self.runner.clean_up_schemas.assert_not_called()
        self.vault.delete_plugin.assert_not_called()
        self.assertTrue(self.config.exists())

    def test_schema_less_removal_preserves_developer_source_and_recovers_completion(
        self,
    ) -> None:
        result = self._remove()
        self.assertEqual(result.status, "removed")
        self.assertTrue((self.root / "plugins/alpha/retained.txt").is_file())
        self.vault.delete_plugin.assert_called_once_with("alpha")
        repeated = self._remove()
        self.assertEqual(repeated.status, "already_removed")
        self.assertEqual(repeated.removal_id, result.removal_id)
        self.runner.clean_up_schemas.assert_called_once()

    def test_external_failure_keeps_fence_and_retries_exact_operation(self) -> None:
        self.apex.remove.side_effect = RuntimeError("external failure")
        with self.assertRaises(PluginInstallationError):
            self._remove(keep_schema=True)
        operation = self.row["removal_id"]
        self.assertEqual(self.row["enabled"], "N")
        self.assertTrue(self.config.exists())
        self.registry.finalize_removal.assert_not_called()
        with self.assertRaisesRegex(PluginInstallationError, "disposition"):
            self._remove()
        self.apex.remove.side_effect = None
        result = self._remove(keep_schema=True)
        self.assertEqual(result.removal_id, operation)
        self.registry.begin_removal.assert_called_once()

    def test_retry_after_file_cleanup_does_not_need_package_files(self) -> None:
        self.registry.finalize_removal.side_effect = RuntimeError(
            "metadata unavailable"
        )
        with self.assertRaises(PluginInstallationError):
            self._remove()
        self.assertFalse(self.installed.exists())
        self.installer._registered_removal_manifest.side_effect = AssertionError(
            "reread deleted package"
        )
        self.registry.finalize_removal.side_effect = self._finalize
        self.vault.delete_plugin.reset_mock()
        self.assertEqual(self._remove().status, "removed")
        self.vault.delete_plugin.assert_called_once_with("alpha")

    def test_unavailable_history_after_failure_preserves_recovery_error(self) -> None:
        def fail_cleanup(*args, **kwargs):
            self.registry.removal_history.side_effect = RuntimeError(
                "private history detail"
            )
            raise RuntimeError("private cleanup detail")

        self.apex.remove.side_effect = fail_cleanup
        with self.assertRaisesRegex(PluginInstallationError, "remains fenced") as error:
            self._remove()
        self.assertNotIn("private", str(error.exception))
        self.assertEqual(self.row["enabled"], "N")
        self.registry.finalize_removal.assert_not_called()

    def test_lost_final_reply_is_recovered_from_completed_operation(self) -> None:
        def lost_reply(**values):
            self._finalize(**values)
            raise RuntimeError("lost reply")

        self.registry.finalize_removal.side_effect = lost_reply
        self.assertEqual(self._remove().status, "removed")
        self.assertIsNone(self.row)

    def test_resource_replacement_during_confirmation_stops_before_fence(self) -> None:
        def change_target(_inventory):
            self.config.rename(self.root / "retained-original")
            self.config.mkdir()
            return True

        with self.assertRaisesRegex(
            PluginInstallationError, "changed during confirmation"
        ):
            self.installer.remove(
                "alpha", confirmed_by="operator", confirm=change_target
            )
        self.registry.begin_removal.assert_not_called()
        self.assertTrue((self.root / "retained-original/retained.txt").exists())

    def test_symlink_inside_managed_directory_blocks_preflight(self) -> None:
        external = self.root / "external.txt"
        external.write_text("preserve")
        (self.config / "link").symlink_to(external)
        with self.assertRaises(PluginInstallationError):
            self._remove()
        self.registry.begin_removal.assert_not_called()
        self.assertEqual(external.read_text(), "preserve")

    def test_each_checkpoint_failure_can_resume_without_recreating_files(self) -> None:
        for stage in (
            "audit_started",
            "apex",
            "database",
            "secrets",
            "directory:configuration",
            "directory:installed",
            "directory:snapshots",
            "routing_cache",
            "files",
        ):
            with self.subTest(stage=stage):
                self.setUp()
                failed = False

                def fail_once(**values):
                    nonlocal failed
                    if stage in values["checkpoints"] and not failed:
                        failed = True
                        raise RuntimeError("checkpoint response failed")
                    self._checkpoint(**values)

                self.registry.checkpoint_removal.side_effect = fail_once
                with self.assertRaises(PluginInstallationError):
                    self._remove()
                operation = self.row["removal_id"]
                self.assertEqual(self.row["enabled"], "N")
                self.assertEqual(self._remove().removal_id, operation)
                self.registry.begin_removal.assert_called_once()

    def test_retry_rejects_a_journal_path_outside_managed_roots(self) -> None:
        self.apex.remove.side_effect = RuntimeError("pause cleanup")
        with self.assertRaises(PluginInstallationError):
            self._remove()
        self.operations[0]["resource_inventory"]["directories"][0]["path"] = str(
            self.root / "plugins"
        )
        self.apex.remove.reset_mock()
        with self.assertRaisesRegex(PluginInstallationError, "unauthorized filesystem"):
            self._remove()
        self.apex.remove.assert_not_called()
        self.assertTrue((self.root / "plugins/alpha/retained.txt").exists())


class PluginRemovalCacheTests(unittest.TestCase):
    """Only the removed plugin's shared routing entries may be invalidated."""

    def test_cache_preview_is_read_only_and_cleanup_preserves_other_plugins(
        self,
    ) -> None:
        import json
        from model.plugin_routing.cache import PluginEmbeddingCache

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cache"
            cache = PluginEmbeddingCache(root)
            path = cache.save(
                "test-model",
                "1",
                {
                    "alpha:read": {"plugin_id": "alpha", "vector": [1.0]},
                    "beta:read": {"plugin_id": "beta", "vector": [2.0]},
                },
            )
            info = root.stat()
            original = path.read_bytes()
            arguments = dict(expected_device=info.st_dev, expected_inode=info.st_ino)
            cache.remove_plugin("alpha", **arguments, dry_run=True)
            self.assertEqual(path.read_bytes(), original)
            cache.remove_plugin("alpha", **arguments)
            cache.remove_plugin("alpha", **arguments)
            self.assertEqual(
                json.loads(path.read_text())["plugins"],
                {
                    "beta:read": {"plugin_id": "beta", "vector": [2.0]},
                },
            )

    def test_cache_replaced_directory_is_not_modified(self) -> None:
        from model.plugin_routing.cache import PluginEmbeddingCache

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "cache"
            root.mkdir()
            info = root.stat()
            root.rename(root.with_name("previous"))
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "changed after authorization"):
                PluginEmbeddingCache(root).remove_plugin(
                    "alpha",
                    expected_device=info.st_dev,
                    expected_inode=info.st_ino,
                )


if __name__ == "__main__":
    unittest.main()
