"""Tests for Orac backup and recovery command wrappers."""
# Author: Clive Bostock
# Date: 2026-05-20
# Description: Verifies backup archive metadata and recovery confirmation behaviour.

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lib.user_security import encrypted_user_credential


BACKUP_SCRIPT = PROJECT_ROOT / "bin" / "orac-backup.sh"
RECOVERY_SCRIPT = PROJECT_ROOT / "bin" / "orac-restore.sh"


class OracBackupRecoveryScriptTests(unittest.TestCase):
    """Tests the host-level backup and recovery shell commands."""

    def test_backup_skip_db_archives_manifest_config_and_schema_metadata(self) -> None:
        """A metadata-only backup should not require Docker."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "backups"
            result = subprocess.run(
                ["bash", str(BACKUP_SCRIPT), "--skip-db", str(target_dir)],
                cwd=PROJECT_ROOT,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            archives = list(target_dir.glob("orac-backup-*.tar.gz"))
            self.assertEqual(len(archives), 1)

            extract_dir = Path(temp_dir) / "extract"
            extract_dir.mkdir()
            with tarfile.open(archives[0], "r:gz") as archive:
                archive.extractall(extract_dir, filter="data")

            root_dirs = [path for path in extract_dir.iterdir() if path.is_dir()]
            self.assertEqual(len(root_dirs), 1)
            backup_root = root_dirs[0]
            manifest = json.loads(
                (backup_root / "backup_manifest.json").read_text(encoding="utf-8")
            )

            requested_schemas = manifest["database"]["requested_schemas"]
            self.assertTrue(manifest["database"]["skip_db"])
            self.assertEqual(
                manifest["vaults"],
                {
                    "files": [],
                    "included": False,
                    "mode": "none",
                    "portable": False,
                    "source_dir": "~/.Orac",
                },
            )
            self.assertIn("orac_core", requested_schemas)
            self.assertIn("orac_api", requested_schemas)
            self.assertIn("orac_code", requested_schemas)
            self.assertIn("orac_ha", requested_schemas)
            self.assertEqual(manifest["database"]["exported_schemas"], [])
            self.assertTrue((backup_root / "plugins.json").exists())
            self.assertTrue((backup_root / "config").is_dir())

    def test_backup_include_vaults_copies_only_allow_listed_base_names(self) -> None:
        """Machine-bound vault inclusion should copy only selected files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            vault_dir = temp_path / "vaults"
            vault_dir.mkdir()
            (vault_dir / "dsn_credentials.ini").write_text(
                "[orac]\nusername = encrypted\n",
                encoding="utf-8",
            )
            (vault_dir / "api_keys.ini").write_text(
                "[service]\napi_key = encrypted\n",
                encoding="utf-8",
            )
            (vault_dir / "not_allowed.ini").write_text(
                "[secret]\nvalue = no\n",
                encoding="utf-8",
            )
            target_dir = temp_path / "backups"

            result = subprocess.run(
                [
                    "bash",
                    str(BACKUP_SCRIPT),
                    "--skip-db",
                    "--include-vaults",
                    str(target_dir),
                ],
                cwd=PROJECT_ROOT,
                env={**os.environ, "ORAC_VAULT_DIR": str(vault_dir)},
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            backup_root = self._extract_single_backup_root(target_dir, temp_path / "extract")
            manifest = json.loads(
                (backup_root / "backup_manifest.json").read_text(encoding="utf-8")
            )

            machine_bound_dir = backup_root / "vaults" / "machine_bound"
            self.assertTrue((machine_bound_dir / "dsn_credentials.ini").exists())
            self.assertTrue((machine_bound_dir / "api_keys.ini").exists())
            self.assertFalse((machine_bound_dir / "not_allowed.ini").exists())
            self.assertEqual(manifest["vaults"]["mode"], "machine_bound")
            self.assertFalse(manifest["vaults"]["portable"])
            self.assertEqual(
                manifest["vaults"]["files"],
                ["dsn_credentials.ini", "api_keys.ini"],
            )

    def test_backup_export_vaults_creates_portable_export(self) -> None:
        """Portable export should create encrypted export artefacts."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            vault_dir = temp_path / "vaults"
            vault_dir.mkdir()
            self._write_sample_vaults(vault_dir)
            passphrase_file = temp_path / "passphrase.txt"
            passphrase_file.write_text("recovery-passphrase\n", encoding="utf-8")
            target_dir = temp_path / "backups"

            result = subprocess.run(
                [
                    "bash",
                    str(BACKUP_SCRIPT),
                    "--skip-db",
                    "--export-vaults",
                    str(target_dir),
                ],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_VAULT_DIR": str(vault_dir),
                    "ORAC_VAULT_EXPORT_PASSPHRASE_FILE": str(passphrase_file),
                },
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            backup_root = self._extract_single_backup_root(target_dir, temp_path / "extract")
            manifest = json.loads(
                (backup_root / "backup_manifest.json").read_text(encoding="utf-8")
            )
            portable_dir = backup_root / "vaults" / "portable"

            self.assertTrue((portable_dir / "vault_export.json.enc").exists())
            self.assertTrue((portable_dir / "vault_export_manifest.json").exists())
            self.assertEqual(manifest["vaults"]["mode"], "portable")
            self.assertTrue(manifest["vaults"]["portable"])
            self.assertEqual(
                manifest["vaults"]["files"],
                ["dsn_credentials.ini", "api_keys.ini"],
            )

    def test_backup_export_vaults_dry_run_does_not_prompt(self) -> None:
        """Dry-run portable vault mode should report mode without passphrase."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    "bash",
                    str(BACKUP_SCRIPT),
                    "--skip-db",
                    "--export-vaults",
                    "--dry-run",
                    str(Path(temp_dir) / "backups"),
                ],
                cwd=PROJECT_ROOT,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Vault mode: portable", result.stdout)
            self.assertNotIn("Vault export passphrase", result.stdout)

    def test_backup_rejects_direct_vault_passphrase_environment(self) -> None:
        """The backup command must not accept passphrases directly in env."""
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {
                **os.environ,
                "ORAC_VAULT_EXPORT_PASSPHRASE": "do-not-use-env-secret",
            }
            result = subprocess.run(
                [
                    "bash",
                    str(BACKUP_SCRIPT),
                    "--skip-db",
                    "--export-vaults",
                    str(Path(temp_dir) / "backups"),
                ],
                cwd=PROJECT_ROOT,
                env=env,
                input="",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "ORAC_VAULT_EXPORT_PASSPHRASE is not supported",
                result.stderr,
            )

    def test_recovery_requires_confirmation_before_docker_work(self) -> None:
        """Recovery should stop before Docker calls unless the operator confirms."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_root = temp_path / "orac-backup-test"
            db_dir = archive_root / "db"
            db_dir.mkdir(parents=True)
            (db_dir / "orac-test.dmp").write_text("placeholder", encoding="utf-8")
            manifest = {
                "backup_format_version": 1,
                "orac_version": "0.0.0-test",
                "database": {
                    "container_name": "orac-db",
                    "pdb": "FREEPDB1",
                    "skip_db": False,
                    "dump_file": "orac-test.dmp",
                    "log_file": "orac-test.log",
                    "requested_schemas": ["orac_core"],
                    "exported_schemas": ["orac_core"],
                    "missing_schemas": [],
                },
                "plugins": [],
            }
            (archive_root / "backup_manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            archive_path = temp_path / "backup.tar.gz"
            with tarfile.open(archive_path, "w:gz") as archive:
                archive.add(archive_root, arcname=archive_root.name)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                input="NO\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("Type RECOVER to continue", combined_output)
            self.assertIn("Restore cancelled", combined_output)
            self.assertNotIn("Preparing Data Pump directory", combined_output)

    def test_recovery_directory_selects_newest_backup_filename(self) -> None:
        """Directory restore should select the newest Orac backup archive by name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            backup_dir = temp_path / "backups"
            backup_dir.mkdir()
            older_archive = self._write_recovery_archive(
                backup_dir,
                archive_name="orac-backup-20260623-101500.tar.gz",
                orac_version="old-version",
            )
            newer_archive = self._write_recovery_archive(
                backup_dir,
                archive_name="orac-backup-20260623-102000.tar.gz",
                orac_version="new-version",
            )
            self._write_recovery_archive(
                backup_dir,
                archive_name="not-an-orac-backup-20260623-103000.tar.gz",
                orac_version="ignored-version",
            )

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), "--dry-run", str(backup_dir)],
                cwd=PROJECT_ROOT,
                env={**os.environ, "ORAC_PYTHON_BIN": sys.executable},
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(f"Selected newest backup archive: {newer_archive}", result.stdout)
            self.assertIn("Backup Orac version : new-version", result.stdout)
            self.assertNotIn(str(older_archive), result.stdout)
            self.assertNotIn("ignored-version", result.stdout)
            self.assertNotIn("Type RECOVER to continue", result.stdout + result.stderr)

    def test_recovery_directory_without_backups_fails_before_prompt(self) -> None:
        """Directory restore should reject directories without Orac backup archives."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            backup_dir = temp_path / "backups"
            backup_dir.mkdir()
            (backup_dir / "backup.tar.gz").write_text("not selected", encoding="utf-8")

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(backup_dir)],
                cwd=PROJECT_ROOT,
                env={**os.environ, "ORAC_PYTHON_BIN": sys.executable},
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("No Orac backup archives found in directory", combined_output)
            self.assertNotIn("Type RECOVER to continue", combined_output)
            self.assertNotIn("Preparing Data Pump directory", combined_output)

    def test_recovery_explicit_archive_path_still_dry_runs(self) -> None:
        """A direct restore archive path should continue to work."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(temp_path)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), "--dry-run", str(archive_path)],
                cwd=PROJECT_ROOT,
                env={**os.environ, "ORAC_PYTHON_BIN": sys.executable},
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Backup Orac version : 0.0.0-test", result.stdout)
            self.assertIn("Dry run only. No database import performed.", result.stdout)
            self.assertNotIn("Selected newest backup archive", result.stdout)

    def test_recovery_makes_copied_dump_readable_before_import(self) -> None:
        """Recovery should fix dump ownership after docker cp and before impdp."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(temp_path)
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            docker_calls = docker_log.read_text(encoding="utf-8").splitlines()
            copy_index = self._first_call_index(docker_calls, " cp ")
            chmod_index = self._first_call_index(docker_calls, "chmod 640")
            import_index = self._first_call_index(docker_calls, " impdp ")

            self.assertLess(copy_index, chmod_index)
            self.assertLess(chmod_index, import_index)
            self.assertIn("chown 54321:54321", docker_calls[chmod_index])
            self.assertIn(
                "/home/oracle/orac/datapump/orac-test.dmp",
                docker_calls[chmod_index],
            )
            self.assertIn("content=data_only", docker_calls[import_index])
            self.assertIn("table_exists_action=truncate", docker_calls[import_index])
            self.assertIn("Restore import complete.", result.stdout)
            self.assertIn("Restore validation complete.", result.stdout)

    def test_recovery_quarantines_plugin_state_before_validation(self) -> None:
        """Recovery should quarantine restored plugin state before final validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(temp_path)
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(
                "Quarantining restored plugin runtime state pending plugin reinstall.",
                result.stdout,
            )
            docker_calls = docker_log.read_text(encoding="utf-8").splitlines()
            import_index = self._first_call_index(docker_calls, " impdp ")
            quarantine_index = self._first_call_index(
                docker_calls,
                "orac_code.restore_recovery_api.quarantine_plugin_state;",
            )
            validation_index = next(
                index
                for index, call in enumerate(
                    docker_calls[quarantine_index + 1 :],
                    quarantine_index + 1,
                )
                if "from all_objects" in call
            )

            self.assertLess(import_index, quarantine_index)
            self.assertLess(quarantine_index, validation_index)

    def test_recovery_preflight_requires_restore_recovery_api(self) -> None:
        """Recovery should fail before import when quarantine API is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(temp_path)
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_FAKE_MISSING_RESTORE_RECOVERY_API": "1",
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn(
                "Restore requires valid ORAC_CODE.RESTORE_RECOVERY_API",
                combined_output,
            )
            docker_log_text = docker_log.read_text(encoding="utf-8")
            self.assertIn("RESTORE_RECOVERY_API", docker_log_text)
            self.assertNotIn(" cp ", f" {docker_log_text} ")
            self.assertNotIn("chmod 640", docker_log_text)
            self.assertNotIn(" impdp ", f" {docker_log_text} ")

    def test_recovery_cleans_dump_when_plugin_quarantine_fails(self) -> None:
        """Recovery should clean the copied dump if post-import quarantine fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(temp_path)
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_FAKE_QUARANTINE_FAIL": "1",
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("Post-restore plugin quarantine failed", combined_output)
            docker_log_text = docker_log.read_text(encoding="utf-8")
            self.assertIn(" impdp ", f" {docker_log_text} ")
            self.assertIn("quarantine_plugin_state", docker_log_text)
            self.assertIn("rm -f", docker_log_text)
            self.assertIn("/home/oracle/orac/datapump/orac-test.dmp", docker_log_text)

    def test_recovery_exits_nonzero_when_validation_fails(self) -> None:
        """Recovery should fail after import when core validation fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(temp_path)
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_FAKE_INVALID_OBJECTS": "1",
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("Restore import complete.", combined_output)
            self.assertIn("## Restore validation summary", combined_output)
            self.assertIn("Invalid objects", combined_output)
            self.assertIn("ORAC_CODE", combined_output)
            self.assertIn("BROKEN_API", combined_output)
            self.assertIn("Restore validation failed", combined_output)
            self.assertNotIn("Restore validation complete.", combined_output)

    def test_recovery_exits_nonzero_when_fk_validation_fails(self) -> None:
        """Recovery should fail after import when core FK validation fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(temp_path)
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_FAKE_FK_ISSUES": "1",
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("Disabled FK constraints", combined_output)
            self.assertIn("Unvalidated FKs", combined_output)
            self.assertIn("Foreign key constraint issues", combined_output)
            self.assertIn("MSG_CONV_FK", combined_output)
            self.assertIn("Restore validation failed", combined_output)

    def test_recovery_compiles_and_validates_plugin_schemas(self) -> None:
        """Recovery should normalize and validate plugin schemas from backup metadata."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(
                temp_path,
                exported_schemas=[
                    "orac_core",
                    "orac_api",
                    "orac_code",
                    "orac_ha",
                ],
                plugins=[
                    {
                        "plugin_id": "home_assistant",
                        "name": "Home Assistant",
                        "version": "1.0.0",
                        "enabled": True,
                        "database_schemas": ["orac_ha"],
                    }
                ],
            )
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            docker_log_text = docker_log.read_text(encoding="utf-8")
            self.assertIn("dbms_utility.compile_schema(", docker_log_text)
            self.assertIn("schema => 'ORAC_HA'", docker_log_text)
            self.assertIn("enable validate constraint", docker_log_text)
            self.assertIn("ORAC_HA", docker_log_text)
            self.assertIn("Restore import complete.", result.stdout)
            self.assertIn("Restore validation complete.", result.stdout)

    def test_recovery_exits_nonzero_when_plugin_validation_fails(self) -> None:
        """Recovery should fail when plugin schema invalid objects are present."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(
                temp_path,
                exported_schemas=[
                    "orac_core",
                    "orac_api",
                    "orac_code",
                    "orac_ha",
                ],
                plugins=[
                    {
                        "plugin_id": "home_assistant",
                        "name": "Home Assistant",
                        "version": "1.0.0",
                        "enabled": True,
                        "database_schemas": ["orac_ha"],
                    }
                ],
            )
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_FAKE_PLUGIN_INVALID_OBJECTS": "1",
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("ORAC_HA", combined_output)
            self.assertIn("BROKEN_PLUGIN", combined_output)
            self.assertIn("Invalid objects", combined_output)
            self.assertIn("Restore validation failed", combined_output)
            self.assertNotIn("Restore validation complete.", combined_output)

    def test_recovery_exits_nonzero_when_plugin_fk_validation_fails(self) -> None:
        """Recovery should fail when plugin schema FKs are not validated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(
                temp_path,
                exported_schemas=[
                    "orac_core",
                    "orac_api",
                    "orac_code",
                    "orac_ha",
                ],
                plugins=[
                    {
                        "plugin_id": "home_assistant",
                        "name": "Home Assistant",
                        "version": "1.0.0",
                        "enabled": True,
                        "database_schemas": ["orac_ha"],
                    }
                ],
            )
            docker_log = temp_path / "docker.log"
            fake_docker = temp_path / "docker"
            self._write_fake_restore_docker(fake_docker)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_DOCKER_BIN": str(fake_docker),
                    "ORAC_FAKE_DOCKER_LOG": str(docker_log),
                    "ORAC_FAKE_PLUGIN_FK_ISSUES": "1",
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                input="RECOVER\n",
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            combined_output = result.stdout + result.stderr
            self.assertIn("ORAC_HA", combined_output)
            self.assertIn("BROKEN_PLUGIN_FK", combined_output)
            self.assertIn("Foreign key constraint issues", combined_output)
            self.assertIn("Restore validation failed", combined_output)
            self.assertNotIn("Restore validation complete.", combined_output)

    def test_recovery_rejects_replace_for_default_data_only_import(self) -> None:
        """Data-only restore should reject replace because metadata is excluded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = self._write_recovery_archive(temp_path)

            result = subprocess.run(
                ["bash", str(RECOVERY_SCRIPT), str(archive_path)],
                cwd=PROJECT_ROOT,
                env={
                    **os.environ,
                    "ORAC_RESTORE_TABLE_EXISTS_ACTION": "replace",
                    "ORAC_PYTHON_BIN": sys.executable,
                },
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "ORAC_RESTORE_TABLE_EXISTS_ACTION=replace requires ORAC_RESTORE_CONTENT=all",
                result.stderr,
            )
            self.assertNotIn("Type RECOVER to continue", result.stdout + result.stderr)

    def test_recovery_script_contains_post_restore_validation(self) -> None:
        """Restore validation should cover restored schemas and plugin-aware normalization."""
        script_text = RECOVERY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("normalize_restored_imported_state", script_text)
        self.assertIn("run_restore_validation", script_text)
        self.assertIn("compile_schema(", script_text)
        self.assertIn("enable validate constraint", script_text)
        self.assertIn("from all_objects", script_text)
        self.assertIn("from all_constraints", script_text)
        self.assertIn('query_invalid_objects "$schemas_path" "$invalid_objects_path"', script_text)
        self.assertIn('query_fk_constraint_issues "$schemas_path" "$fk_issues_path"', script_text)
        self.assertIn('recompile_schema_list "$schemas_path"', script_text)
        self.assertIn('generate_fk_enable_sql "$schemas_path" "$fk_enable_sql"', script_text)
        self.assertIn("status <> 'VALID'", script_text)
        self.assertIn("status <> 'ENABLED'", script_text)
        self.assertIn("validated <> 'VALIDATED'", script_text)
        self.assertNotIn("ORAC_HA", script_text)

    def test_recovery_validation_includes_key_core_row_counts(self) -> None:
        """Restore validation should report key ORAC_CORE table counts."""
        script_text = RECOVERY_SCRIPT.read_text(encoding="utf-8")

        for table_name in (
            "USERS",
            "CONVERSATIONS",
            "MESSAGES",
            "USER_PREFERENCES",
            "LLM_REGISTRY",
            "TTS_VOICES",
            "ORAC_PERSONALITIES",
            "PREFERENCE_DEFINITIONS",
            "MODEL_GENERATION_PRESETS",
        ):
            self.assertIn(f'query_core_table_count "{table_name}"', script_text)

    def _extract_single_backup_root(self, target_dir: Path, extract_dir: Path) -> Path:
        """Extract the only backup archive in a target directory."""
        archives = list(target_dir.glob("orac-backup-*.tar.gz"))
        self.assertEqual(len(archives), 1)
        extract_dir.mkdir()
        with tarfile.open(archives[0], "r:gz") as archive:
            archive.extractall(extract_dir, filter="data")

        root_dirs = [path for path in extract_dir.iterdir() if path.is_dir()]
        self.assertEqual(len(root_dirs), 1)
        return root_dirs[0]

    def _write_recovery_archive(
        self,
        temp_path: Path,
        exported_schemas: list[str] | None = None,
        plugins: list[dict[str, object]] | None = None,
        archive_name: str = "backup.tar.gz",
        orac_version: str = "0.0.0-test",
    ) -> Path:
        """Create a minimal database restore archive."""
        archive_root = temp_path / "orac-backup-test"
        db_dir = archive_root / "db"
        db_dir.mkdir(parents=True, exist_ok=True)
        (db_dir / "orac-test.dmp").write_text("placeholder", encoding="utf-8")
        if exported_schemas is None:
            exported_schemas = ["orac_core"]
        if plugins is None:
            plugins = []
        manifest = {
            "backup_format_version": 1,
            "orac_version": orac_version,
            "database": {
                "container_name": "orac-db",
                "pdb": "FREEPDB1",
                "skip_db": False,
                "dump_file": "orac-test.dmp",
                "log_file": "orac-test.log",
                "requested_schemas": exported_schemas,
                "exported_schemas": exported_schemas,
                "missing_schemas": [],
            },
            "plugins": plugins,
        }
        (archive_root / "backup_manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        archive_path = temp_path / archive_name
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(archive_root, arcname=archive_root.name)
        return archive_path

    def _first_call_index(self, docker_calls: list[str], pattern: str) -> int:
        """Return the first fake Docker call index containing a pattern."""
        for index, call in enumerate(docker_calls):
            if pattern in f" {call} ":
                return index
        self.fail(f"Fake Docker call not found: {pattern}")

    def _write_fake_restore_docker(self, docker_path: Path) -> None:
        """Write a fake Docker binary that simulates restore SQL calls."""
        docker_path.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    'printf "%s\\n" "$*" >> "$ORAC_FAKE_DOCKER_LOG"',
                    'case "$1" in',
                    "  exec)",
                    '    if [[ "$*" == *"sqlplus"* ]]; then',
                    "      sql_input=$(cat)",
                    '      printf "%s\\n" "$sql_input" >> "$ORAC_FAKE_DOCKER_LOG"',
                    '      if [[ "$sql_input" == *"RESTORE_RECOVERY_API"* ]]; then',
                    '        if [[ "${ORAC_FAKE_MISSING_RESTORE_RECOVERY_API:-0}" != "1" ]]; then',
                    '          printf "PACKAGE\\tVALID\\n"',
                    '          printf "PACKAGE BODY\\tVALID\\n"',
                    "        fi",
                    '      elif [[ "$sql_input" == *"quarantine_plugin_state"* ]]; then',
                    '        if [[ "${ORAC_FAKE_QUARANTINE_FAIL:-0}" == "1" ]]; then',
                    '          printf "ORA-06550: simulated quarantine failure\\n" >&2',
                    "          exit 1",
                    "        fi",
                    '      elif [[ "$sql_input" == *"from all_objects"* ]]; then',
                    '        if [[ "${ORAC_FAKE_INVALID_OBJECTS:-0}" == "1" ]]; then',
                    '          printf "ORAC_CODE\\tPACKAGE BODY\\tBROKEN_API\\tINVALID\\n"',
                    "        fi",
                    '        if [[ "${ORAC_FAKE_PLUGIN_INVALID_OBJECTS:-0}" == "1" ]]; then',
                    '          printf "ORAC_HA\\tPACKAGE\\tBROKEN_PLUGIN\\tINVALID\\n"',
                    "        fi",
                    "      elif [[ \"$sql_input\" == *\"from all_constraints\"* && \"$sql_input\" == *\"validated\"* ]]; then",
                    '        if [[ "${ORAC_FAKE_FK_ISSUES:-0}" == "1" ]]; then',
                    '          printf "ORAC_CORE\\tMESSAGES\\tMSG_CONV_FK\\tDISABLED\\tNOT VALIDATED\\n"',
                    "        fi",
                    '        if [[ "${ORAC_FAKE_PLUGIN_FK_ISSUES:-0}" == "1" ]]; then',
                    '          printf "ORAC_HA\\tHA_ENTITIES\\tBROKEN_PLUGIN_FK\\tDISABLED\\tNOT VALIDATED\\n"',
                    "        fi",
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.USERS"* ]]; then',
                    '        printf "1\\n"',
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.CONVERSATIONS"* ]]; then',
                    '        printf "13\\n"',
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.MESSAGES"* ]]; then',
                    '        printf "209\\n"',
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.USER_PREFERENCES"* ]]; then',
                    '        printf "19\\n"',
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.LLM_REGISTRY"* ]]; then',
                    '        printf "18\\n"',
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.TTS_VOICES"* ]]; then',
                    '        printf "78\\n"',
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.ORAC_PERSONALITIES"* ]]; then',
                    '        printf "6\\n"',
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.PREFERENCE_DEFINITIONS"* ]]; then',
                    '        printf "19\\n"',
                    '      elif [[ "$sql_input" == *"from ORAC_CORE.MODEL_GENERATION_PRESETS"* ]]; then',
                    '        printf "8\\n"',
                    "      fi",
                    "      exit 0",
                    "    fi",
                    "    exit 0",
                    "    ;;",
                    "  cp)",
                    "    exit 0",
                    "    ;;",
                    "esac",
                    "exit 0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        docker_path.chmod(0o755)

    def _write_sample_vaults(self, vault_dir: Path) -> None:
        """Write decryptable sample vault files."""
        dsn_config = configparser.ConfigParser()
        dsn_config["orac"] = {
            "username": encrypted_user_credential("orac_user"),
            "password": encrypted_user_credential("orac_password"),
            "resource_id": "orac-pdb",
        }
        with (vault_dir / "dsn_credentials.ini").open("w", encoding="utf-8") as handle:
            dsn_config.write(handle)

        api_config = configparser.ConfigParser()
        api_config["example/service"] = {
            "api_key": encrypted_user_credential("api-secret"),
        }
        with (vault_dir / "api_keys.ini").open("w", encoding="utf-8") as handle:
            api_config.write(handle)


if __name__ == "__main__":
    unittest.main()
