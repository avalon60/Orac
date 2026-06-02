"""Tests for Orac Compose control helper logic."""
# Author: Clive Bostock
# Date: 31-May-2026
# Description: Verifies Compose profile selection and stack path validation.

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CTL_SCRIPT = PROJECT_ROOT / "bin" / "orac-ctl.sh"
DB_DEPLOY_SCRIPT = PROJECT_ROOT / "bin" / "orac-db-deploy.sh"
ORACLE_SETUP_DIR = PROJECT_ROOT / "resources" / "docker" / "oracle" / "setup"
ORACLE_STARTUP_DIR = PROJECT_ROOT / "resources" / "docker" / "oracle" / "startup"
ORACLE_COMPOSE_FILE = PROJECT_ROOT / "resources" / "docker" / "oracle" / "docker-compose.yaml"
SEARXNG_SETTINGS_FILE = PROJECT_ROOT / "resources" / "docker" / "oracle" / "searxng" / "settings.yml"


class OracCtlComposeTests(unittest.TestCase):
    """Tests shell helper behaviour without touching Docker state."""

    def test_default_stack_paths_are_relative_to_orac_base(self) -> None:
        """Default Compose paths should resolve from the orac-ctl.sh location."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                (
                    f"ORAC_CTL_LIB_ONLY=1 source {CTL_SCRIPT}; "
                    "printf 'stack=%s\n' \"$ORAC_STACK_DIR\"; "
                    "printf 'compose=%s\n' \"$ORAC_COMPOSE_FILE\"; "
                    "printf 'env=%s\n' \"$ORAC_ENV_FILE\""
                ),
            ],
            cwd=Path("/tmp"),
            env={
                key: value
                for key, value in os.environ.items()
                if key
                not in {
                    "ORAC_STACK_DIR",
                    "ORAC_COMPOSE_FILE",
                    "ORAC_ENV_FILE",
                }
            },
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn(
            f"stack={PROJECT_ROOT / 'resources' / 'docker' / 'oracle'}",
            result.stdout,
        )
        self.assertIn(
            f"compose={PROJECT_ROOT / 'resources' / 'docker' / 'oracle' / 'docker-compose.yaml'}",
            result.stdout,
        )
        self.assertIn(
            f"env={PROJECT_ROOT / 'resources' / 'config' / 'orac.env'}",
            result.stdout,
        )

    def test_profile_selection_activates_voice_and_search(self) -> None:
        """Docker Kokoro and autostarted SearXNG should activate both profiles."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = self._write_config(
                temp_path,
                voice_runtime="docker-cpu",
                searxng_autostart="true",
            )
            stack_dir = self._write_stack_files(temp_path)

            result = self._run_helper(
                config_file=config_file,
                stack_dir=stack_dir,
                script="""
                determine_compose_profiles
                printf 'profiles=%s\n' "$(compose_profiles_text)"
                printf 'kokoro_image=%s\n' "$KOKORO_IMAGE"
                compose_command_preview "${COMPOSE_PROFILE_ARGS[@]}" up -d
                """,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("profiles=voice search", result.stdout)
            self.assertIn(
                "kokoro_image=ghcr.io/remsky/kokoro-fastapi-cpu:latest",
                result.stdout,
            )
            self.assertIn("--profile voice --profile search up -d", result.stdout)

    def test_external_kokoro_runtime_does_not_activate_voice_profile(self) -> None:
        """External Kokoro is checked by URL and not managed by Compose."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = self._write_config(
                temp_path,
                voice_runtime="external",
                searxng_autostart="false",
            )
            stack_dir = self._write_stack_files(temp_path)

            result = self._run_helper(
                config_file=config_file,
                stack_dir=stack_dir,
                script="""
                determine_compose_profiles
                printf 'profiles=%s\n' "$(compose_profiles_text)"
                printf 'external=%s\n' "$KOKORO_EXTERNAL_ENABLED"
                printf 'readiness=%s\n' "$KOKORO_READINESS_URL"
                """,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("profiles=none", result.stdout)
            self.assertIn("external=1", result.stdout)
            self.assertIn(
                "readiness=http://127.0.0.1:8880/v1/audio/voices",
                result.stdout,
            )

    def test_unsupported_kokoro_runtime_warns_and_skips_voice_profile(self) -> None:
        """Unsupported Kokoro runtimes should not create a Compose profile."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = self._write_config(
                temp_path,
                voice_runtime="podman",
                searxng_autostart="false",
            )
            stack_dir = self._write_stack_files(temp_path)

            result = self._run_helper(
                config_file=config_file,
                stack_dir=stack_dir,
                script="""
                determine_compose_profiles
                printf 'profiles=%s\n' "$(compose_profiles_text)"
                printf 'voice=%s\n' "$VOICE_PROFILE_ENABLED"
                """,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Unsupported tts_kokoro_runtime='podman'", result.stdout)
            self.assertIn("profiles=none", result.stdout)
            self.assertIn("voice=0", result.stdout)

    def test_missing_stack_files_are_reported(self) -> None:
        """Missing Compose inputs should be validation failures, not Docker calls."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_file = self._write_config(
                temp_path,
                voice_runtime="docker-cpu",
                searxng_autostart="false",
            )
            stack_dir = temp_path / "missing-stack"

            result = self._run_helper(
                config_file=config_file,
                stack_dir=stack_dir,
                env_file=stack_dir / "orac.env",
                script="""
                if require_compose_inputs; then
                  printf 'unexpected-success\n'
                else
                  printf 'validation-failed\n'
                fi
                """,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("Missing Compose file", result.stdout)
            self.assertIn("Missing Compose env file", result.stdout)
            self.assertIn("validation-failed", result.stdout)

    def test_orac_searxng_compose_mount_enables_json_format(self) -> None:
        """Compose-managed SearXNG should allow Orac's JSON search endpoint."""
        compose_text = ORACLE_COMPOSE_FILE.read_text(encoding="utf-8")
        settings_text = SEARXNG_SETTINGS_FILE.read_text(encoding="utf-8")

        self.assertIn("./searxng/settings.yml:/etc/searxng/settings.yml", compose_text)
        self.assertIn("formats:", settings_text)
        self.assertIn("- html", settings_text)
        self.assertIn("- json", settings_text)
        self.assertIn("secret_key:", settings_text)
        self.assertIn("SEARXNG_SECRET", compose_text)

    def _run_helper(
        self,
        *,
        config_file: Path,
        stack_dir: Path,
        env_file: Path | None = None,
        script: str,
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "ORAC_CTL_LIB_ONLY": "1",
            "ORAC_CONFIG_FILE": str(config_file),
            "ORAC_STACK_DIR": str(stack_dir),
        }
        if env_file is not None:
            env["ORAC_ENV_FILE"] = str(env_file)
        command = f"source {CTL_SCRIPT}; {textwrap.dedent(script)}"
        return subprocess.run(
            ["bash", "-c", command],
            cwd=PROJECT_ROOT,
            env=env,
            check=False,
            text=True,
            capture_output=True,
        )

    def _write_stack_files(self, temp_path: Path) -> Path:
        stack_dir = temp_path / "stack"
        stack_dir.mkdir()
        (stack_dir / "docker-compose.yaml").write_text(
            "services:\n  orac-db:\n    image: orac:latest\n",
            encoding="utf-8",
        )
        (stack_dir / "orac.env").write_text(
            "\n".join(
                [
                    "COMPOSE_PROJECT_NAME=orac",
                    "ORAC_DB_CONTAINER_NAME=orac-db",
                    "ORAC_IMAGE_NAME=orac",
                    "ORAC_IMAGE_TAG=latest",
                    "ORADATA_DIR=/tmp/oradata",
                    "PORT_SQLNET=1521",
                    "PORT_HTTP=8042",
                    "PORT_EM=5500",
                    "",
                ],
            ),
            encoding="utf-8",
        )
        return stack_dir

    def _write_config(
        self,
        temp_path: Path,
        *,
        voice_runtime: str,
        searxng_autostart: str,
    ) -> Path:
        config_file = temp_path / "orac.ini"
        config_file.write_text(
            textwrap.dedent(
                f"""
                [voice]
                tts_engine = kokoro
                tts_kokoro_autostart = true
                tts_kokoro_runtime = {voice_runtime}
                tts_kokoro_container_name = orac-kokoro
                tts_kokoro_host = 127.0.0.1
                tts_kokoro_port = 8880
                tts_kokoro_base_url = http://127.0.0.1:8880/v1
                tts_kokoro_image =

                [retrieval]
                internet_search_enabled = true
                default_search_provider = searxng

                [retrieval.searxng]
                autostart = {searxng_autostart}
                host = 127.0.0.1
                port = 8888
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return config_file


class OracDbDeployComposeTests(unittest.TestCase):
    """Tests DB deploy script Compose path resolution without Docker mutation."""

    def test_default_stack_paths_are_relative_to_orac_base(self) -> None:
        """DB deploy defaults should match the script-relative Compose layout."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                (
                    f"ORAC_DB_DEPLOY_LIB_ONLY=1 source {DB_DEPLOY_SCRIPT}; "
                    "printf 'stack=%s\n' \"$ORAC_STACK_DIR\"; "
                    "printf 'compose=%s\n' \"$ORAC_COMPOSE_FILE\"; "
                    "printf 'env=%s\n' \"$ORAC_ENV_FILE\""
                ),
            ],
            cwd=Path("/tmp"),
            env={
                key: value
                for key, value in os.environ.items()
                if key
                not in {
                    "ORAC_STACK_DIR",
                    "ORAC_COMPOSE_FILE",
                    "ORAC_ENV_FILE",
                }
            },
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn(
            f"stack={PROJECT_ROOT / 'resources' / 'docker' / 'oracle'}",
            result.stdout,
        )
        self.assertIn(
            f"compose={PROJECT_ROOT / 'resources' / 'docker' / 'oracle' / 'docker-compose.yaml'}",
            result.stdout,
        )
        self.assertIn(
            f"env={PROJECT_ROOT / 'resources' / 'config' / 'orac.env'}",
            result.stdout,
        )

    def test_compose_command_uses_overridden_stack_files(self) -> None:
        """DB deploy compose_cmd should honour ORAC_COMPOSE_FILE and ORAC_ENV_FILE."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            compose_file = temp_path / "compose.yaml"
            env_file = temp_path / "stack.env"

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    textwrap.dedent(
                        f"""
                        docker() {{ printf 'docker'; printf ' %s' "$@"; printf '\\n'; }}
                        export ORAC_DB_DEPLOY_LIB_ONLY=1
                        export ORAC_COMPOSE_FILE={compose_file}
                        export ORAC_ENV_FILE={env_file}
                        source {DB_DEPLOY_SCRIPT}
                        compose_cmd up -d orac-db
                        """
                    ),
                ],
                cwd=PROJECT_ROOT,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(
                f"docker compose --env-file {env_file} -f {compose_file} up -d orac-db",
                result.stdout.strip(),
            )

    def test_deploy_wait_fails_fast_on_orac_setup_failure_marker(self) -> None:
        """DB deploy wait loop should stop immediately on explicit setup failure."""
        result = subprocess.run(
            [
                "bash",
                "-c",
                textwrap.dedent(
                    f"""
                    docker() {{
                      if [[ "$1" == "logs" ]]; then
                        printf 'ORAC_ORDS_SETUP_FAILED: test failure\\n'
                        return 0
                      fi
                      printf 'unexpected docker call: %s\\n' "$*" >&2
                      return 1
                    }}
                    export ORAC_DB_DEPLOY_LIB_ONLY=1
                    source {DB_DEPLOY_SCRIPT}
                    if wait_for_orac_deploy; then
                      printf 'unexpected-success\\n'
                    else
                      printf 'wait-failed\\n'
                    fi
                    """
                ),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("Matched marker: ORAC_ORDS_SETUP_FAILED", result.stdout)
        self.assertIn("wait-failed", result.stdout)


class OracleSetupScriptContractTests(unittest.TestCase):
    """Static checks for Oracle container setup script safety."""

    def test_required_setup_scripts_exist(self) -> None:
        """Core setup phases should be present in the image input directory."""
        expected_scripts = {
            "000-started.sh",
            "010-apex-install.sh",
            "020-setup-ords.sh",
            "035-orac-schema_and_apps.sh",
            "999-complete.sh",
        }

        actual_scripts = {path.name for path in ORACLE_SETUP_DIR.glob("*.sh")}
        self.assertTrue(
            expected_scripts <= actual_scripts,
            f"Missing setup scripts: {sorted(expected_scripts - actual_scripts)}",
        )

    def test_duplicate_copy_setup_scripts_are_rejected(self) -> None:
        """Accidental editor-copy scripts must not be copied into Oracle setup."""
        duplicate_scripts = sorted(ORACLE_SETUP_DIR.glob("* (copy).sh"))
        self.assertEqual(duplicate_scripts, [])

    def test_sourced_setup_scripts_do_not_use_direct_shell_exit(self) -> None:
        """Oracle sources setup scripts, so direct shell exit can abort the runner."""
        checked_scripts = sorted(ORACLE_SETUP_DIR.glob("*.sh")) + sorted(
            ORACLE_STARTUP_DIR.glob("*.sh")
        )
        offenders: list[str] = []

        for script_path in checked_scripts:
            for line_number, line in self._shell_lines_outside_heredocs(script_path):
                if re.match(r"^\s*exit\b", line):
                    offenders.append(f"{script_path.relative_to(PROJECT_ROOT)}:{line_number}")

        self.assertEqual(offenders, [])

    def test_ords_setup_does_not_delete_logs_directory(self) -> None:
        """ORDS setup may clear config but must not remove root-owned log dirs."""
        script = (ORACLE_SETUP_DIR / "020-setup-ords.sh").read_text(encoding="utf-8")

        self.assertNotRegex(script, r"rm\s+-[^\n]*\$\{?ORDS_LOG\}?")
        self.assertNotRegex(script, r"rm\s+-[^\n]*/home/oracle/orac/logs")
        self.assertIn('mkdir -p "${ORDS_CONF}" "${ORDS_LOG}"', script)

    def test_ords_setup_uses_sys_installer_and_checks_install_log(self) -> None:
        """ORDS setup must not accept a partial ORDS install as success."""
        script = (ORACLE_SETUP_DIR / "020-setup-ords.sh").read_text(encoding="utf-8")

        self.assertIn('ORDS_DB_ADMIN_USER="${ORDS_DB_ADMIN_USER:-SYS}"', script)
        self.assertIn("ORDS install log contains Oracle errors", script)
        self.assertRegex(script, r"grep\s+-Eiq .*ORA-\[0-9\]")
        self.assertIn("owner = 'ORDS_METADATA'", script)
        self.assertIn("ORDS metadata objects are not VALID", script)

    def test_completion_requires_valid_ords_metadata(self) -> None:
        """The final deployment marker must require valid ORDS metadata."""
        script = (ORACLE_SETUP_DIR / "999-complete.sh").read_text(encoding="utf-8")

        self.assertIn("owner = 'ORDS_METADATA'", script)
        self.assertIn("ORDS metadata objects are not VALID", script)

    def test_deploy_verification_requires_ords_metadata_and_http_ready(self) -> None:
        """Deploy marker verification must reject config-only ORDS state."""
        script = DB_DEPLOY_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("verify_container_ords_config()", script)
        self.assertIn("wait_for_ords_apex_app", script)
        self.assertIn("owner = ", script)
        self.assertIn("ORDS_METADATA", script)
        self.assertIn("ORDS metadata objects are not VALID", script)
        self.assertIn("APEX_APP_ID: 1042", script)

    def test_startup_refreshes_listener_after_container_recreation(self) -> None:
        """Startup should repair persisted listener hostnames before dbwait."""
        script = (ORACLE_STARTUP_DIR / "005-refresh-listener.sh").read_text(encoding="utf-8")

        self.assertIn("ORAC_LISTENER_REFRESH_COMPLETE", script)
        self.assertIn("sed -i -E", script)
        self.assertIn("lsnrctl start LISTENER", script)
        self.assertIn("alter system register", script)

    def _shell_lines_outside_heredocs(self, path: Path) -> list[tuple[int, str]]:
        """Return shell-source lines, ignoring SQL heredoc bodies."""
        heredoc_end = ""
        shell_lines: list[tuple[int, str]] = []
        heredoc_pattern = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")

        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if heredoc_end:
                if line.strip() == heredoc_end:
                    heredoc_end = ""
                continue

            shell_lines.append((line_number, line))
            match = heredoc_pattern.search(line)
            if match:
                heredoc_end = match.group(1)

        return shell_lines


if __name__ == "__main__":
    unittest.main()
