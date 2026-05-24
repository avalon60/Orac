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
