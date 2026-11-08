"""Plugin-owned database payload validation, packaging, and deployment."""

# Author: Clive Bostock
# Date: 2026-06-03
# Description: Validates and deploys plugin-local database schema bundles.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import gzip
import io
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile
from typing import TYPE_CHECKING, Any, Callable, Literal, Protocol
from xml.etree import ElementTree

if TYPE_CHECKING:
    from model.plugin_routing.models import PluginManifest

__author__ = "Clive Bostock"
__date__ = "2026-06-03"
__description__ = "Validates, packages, stages, and deploys plugin database payloads."


PROTECTED_ORAC_SCHEMAS = (
    "orac",
    "orac_apx_pub",
    "orac_core",
    "orac_api",
    "orac_code",
    "orac_plugin",
)

# Host-approved owner privileges, keyed by both registered plugin and schema.
# Plugin SQL/manifests cannot request extra system privileges. These grants are
# reconciled on every deployment; failed payloads retain them for repair. Never
# revoke rights here: DDL commits and pre-existing grants have no provenance.
_PLUGIN_SCHEMA_EXTRA_PRIVILEGES = {
    ("orac_chess", "ORAC_CHESS"): ("create mle",),
}


PLUGIN_BRIDGE_API_CATALOG = {
    "knowledge_scope_validation": {
        "owner": "ORAC_PLUGIN",
        "object_name": "KNOWLEDGE_SCOPE_VALIDATION_API",
        "object_type": "PACKAGE",
        "privilege": "EXECUTE",
    },
    "knowledge_tag_validation": {
        "owner": "ORAC_PLUGIN",
        "object_name": "KNOWLEDGE_TAG_VALIDATION_API",
        "object_type": "PACKAGE",
        "privilege": "EXECUTE",
    },
}
_PLUGIN_BRIDGE_CATALOG_FIELDS = frozenset(
    {"owner", "object_name", "object_type", "privilege"}
)
_PLUGIN_BRIDGE_GRANTABLE_PRIVILEGES = {
    "PACKAGE": frozenset({"EXECUTE"}),
}

PLUGIN_DB_DEPLOYMENT_STATUSES = (
    "not_required",
    "optional_missing",
    "deployed",
    "already_deployed",
    "missing_disabled",
    "validation_failed",
    "deployment_failed",
)

PluginDatabaseDeploymentStatus = Literal[
    "not_required",
    "optional_missing",
    "deployed",
    "already_deployed",
    "missing_disabled",
    "validation_failed",
    "deployment_failed",
]

_SCANNED_DDL_SUFFIXES = {".sql", ".pks", ".pkb", ".pls", ".plb"}
_SCANNED_CHANGELOG_SUFFIXES = {".xml"}
_PROTECTED_SCHEMA_REFERENCE = re.compile(
    r"(?<![a-z0-9_])\"?("
    + "|".join(
        re.escape(schema)
        for schema in PROTECTED_ORAC_SCHEMAS
        if schema != "orac_plugin"
    )
    + r")\"?\s*\.",
    re.IGNORECASE,
)
_SCHEMA_QUALIFIED_REFERENCE = re.compile(
    r"(?<![a-z0-9_])\"?([a-z][a-z0-9_]*)\"?\s*\.",
    re.IGNORECASE,
)
_PLUGIN_BRIDGE_REFERENCE = re.compile(
    r'(?<![a-z0-9_])"?orac_plugin"?\s*\.\s*' r'"?([a-z][a-z0-9_]*)"?',
    re.IGNORECASE,
)
_PUBLIC_SYNONYM = re.compile(
    r"\bcreate\s+(?:or\s+replace\s+)?public\s+synonym\b",
    re.IGNORECASE,
)
_PRIVATE_SYNONYM_TARGET = re.compile(
    r"\bcreate\s+(?:or\s+replace\s+)?synonym\s+"
    r"(?:\"?[a-z][a-z0-9_]*\"?\s*\.\s*)?\"?[a-z][a-z0-9_]*\"?\s+"
    r"for\s+\"?([a-z][a-z0-9_]*)\"?\s*\.",
    re.IGNORECASE,
)
_GRANT_STATEMENT = re.compile(
    r"\bgrant\s+(.+?)\s+on\s+"
    r"\"?([a-z][a-z0-9_]*)\"?\s*\.\s*\"?([a-z][a-z0-9_]*)\"?"
    r"\s+to\s+\"?([a-z][a-z0-9_]*)\"?",
    re.IGNORECASE | re.DOTALL,
)
_DDL_OWNER_STATEMENT = re.compile(
    r"\b(?:create|create\s+or\s+replace|alter|drop)\s+"
    r"(?:editionable\s+|noneditionable\s+)?"
    r"(?:table|view|materialized\s+view|package\s+body|package|procedure|"
    r"function|trigger|sequence|type\s+body|type|synonym|context|role|index)\s+"
    r"\"?([a-z][a-z0-9_]*)\"?\s*\.",
    re.IGNORECASE,
)
_APEX_PATH_PARTS = {"apex", "orac_apps", "orac_ws"}
_ALLOWED_PLUGIN_GRANTEES = {"orac_plugin", "orac_apx_pub"}
_ALLOWED_SHARED_PLUGIN_REFERENCE_SCHEMAS = {"orac_plugin"}
_DEPLOYED_OBJECT_FOLDERS = {
    "function": "FUNCTION",
    "materialized_view": "MATERIALIZED VIEW",
    "package_body": "PACKAGE BODY",
    "package_spec": "PACKAGE",
    "procedure": "PROCEDURE",
    "sequence": "SEQUENCE",
    "table": "TABLE",
    "trigger": "TRIGGER",
    "type_body": "TYPE BODY",
    "type_spec": "TYPE",
    "view": "VIEW",
}


class PluginDatabaseDeploymentError(RuntimeError):
    """Raised when plugin database deployment cannot continue safely."""


class PluginDatabaseValidationError(PluginDatabaseDeploymentError):
    """Raised when plugin database payload validation fails."""


def validate_plugin_bridge_api_catalog(
    catalog: Mapping[str, Mapping[str, str]] = PLUGIN_BRIDGE_API_CATALOG,
) -> None:
    """Validate the host-owned bridge dependency allowlist.

    Args:
        catalog: Dependency identifiers mapped to fixed grant metadata.

    Raises:
        PluginDatabaseValidationError: If the catalogue can express an unsafe
            or ambiguous grant.
    """
    targets: dict[tuple[str, str, str, str], str] = {}
    for dependency_id, dependency in catalog.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", dependency_id):
            raise PluginDatabaseValidationError(
                f"Invalid plugin bridge API dependency id: {dependency_id}"
            )
        if set(dependency) != _PLUGIN_BRIDGE_CATALOG_FIELDS:
            raise PluginDatabaseValidationError(
                "Plugin bridge API catalogue entry must contain only owner, "
                f"object_name, object_type, and privilege: {dependency_id}"
            )
        if any(
            not isinstance(dependency[field], str) or not dependency[field]
            for field in _PLUGIN_BRIDGE_CATALOG_FIELDS
        ):
            raise PluginDatabaseValidationError(
                f"Plugin bridge API catalogue entry is incomplete: {dependency_id}"
            )

        owner = dependency["owner"].upper()
        object_name = dependency["object_name"].upper()
        object_type = dependency["object_type"].upper()
        privilege = dependency["privilege"].upper()
        if owner != "ORAC_PLUGIN":
            raise PluginDatabaseValidationError(
                "Plugin bridge API catalogue owner must be ORAC_PLUGIN: "
                f"{dependency_id}"
            )
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", object_name):
            raise PluginDatabaseValidationError(
                f"Invalid plugin bridge API object name: {dependency_id}"
            )
        grantable = _PLUGIN_BRIDGE_GRANTABLE_PRIVILEGES.get(object_type)
        if grantable is None or privilege not in grantable:
            raise PluginDatabaseValidationError(
                "Plugin bridge API catalogue privilege is not grantable for "
                f"{object_type}: {dependency_id}={privilege}"
            )

        target = (owner, object_name, object_type, privilege)
        if target in targets:
            raise PluginDatabaseValidationError(
                "Plugin bridge API catalogue contains duplicate targets: "
                f"{targets[target]}, {dependency_id}"
            )
        targets[target] = dependency_id


@dataclass(frozen=True)
class ProtectedSchemaReference:
    """A forbidden protected schema reference found in plugin DDL."""

    path: Path
    line_number: int
    schema_name: str
    line_text: str

    def describe(self) -> str:
        """Return a concise human-readable violation description."""
        return (
            f"{self.path}:{self.line_number}: protected schema "
            f"'{self.schema_name}' referenced in: {self.line_text.strip()}"
        )


@dataclass(frozen=True)
class PluginDatabaseArchive:
    """Archive metadata produced for a plugin database payload."""

    archive_path: Path
    payload_checksum: str
    archive_checksum: str
    manifest: dict[str, Any]


@dataclass(frozen=True)
class PluginDatabaseDeploymentResult:
    """Outcome of one plugin database deployment eligibility check."""

    plugin_id: str
    status: PluginDatabaseDeploymentStatus
    eligible: bool
    message: str
    archive_path: Path | None = None
    payload_checksum: str | None = None
    archive_checksum: str | None = None


class PluginDatabaseSession(Protocol):
    """Minimal database session protocol used for plugin schema provisioning."""

    def cursor(self) -> Any:
        """Return a context-managed Oracle cursor."""

    def commit(self) -> None:
        """Commit the current transaction."""

    def close(self) -> None:
        """Close the database session."""


class PluginDatabaseSchemaProvisioner:
    """Creates missing plugin-owned Oracle schemas before payload deployment."""

    _SCHEMA_GRANTS = (
        "create session",
        "create table",
        "create view",
        "create sequence",
        "create procedure",
        "create trigger",
        "create type",
        "create synonym",
    )

    def __init__(
        self,
        *,
        connection_name: str = "orac",
        project_identifier: str | None = None,
        session_factory: Callable[[], PluginDatabaseSession] | None = None,
        password_factory: Callable[[], str] | None = None,
        admin_runner: DockerPluginDatabaseRunner | None = None,
        logger: Any | None = None,
    ) -> None:
        """Initialise the plugin schema provisioner.

        :param connection_name: Saved DSN connection used for admin DDL.
        :param project_identifier: Credential-store project identifier.
        :param session_factory: Injectable database session factory for tests.
        :param password_factory: Injectable password generator for new schemas.
        :param logger: Optional Orac logger.
        """
        self._connection_name = connection_name
        self._project_identifier = project_identifier
        self._session_factory = session_factory
        self._password_factory = password_factory or (lambda: secrets.token_urlsafe(32))
        self._logger = logger
        self._admin_runner = admin_runner

    def ensure_schemas(self, manifest: PluginManifest) -> None:
        """Ensure every declared plugin database schema exists.

        :param manifest: Plugin manifest with database schema declarations.
        :raises PluginDatabaseDeploymentError: when schema provisioning fails.
        """
        if not manifest.database_schemas:
            return

        if self._session_factory is None:
            # Real provisioning uses the existing container administrator,
            # never the application's runtime DSN or name-only adoption.
            runner = self._admin_runner or DockerPluginDatabaseRunner(
                logger=self._logger
            )
            runner.provision_schemas(manifest)
            return

        session: PluginDatabaseSession | None = None
        try:
            session = self._connect()
            with session.cursor() as cursor:
                for block in _schema_provisioning_blocks(
                    manifest, oracle_pdb="FREEPDB1"
                ):
                    cursor.execute(block)
            session.commit()
        except Exception as exc:
            raise PluginDatabaseDeploymentError(
                f"Plugin database schema provisioning failed: {exc}"
            ) from exc
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass

    def _connect(self) -> PluginDatabaseSession:
        """Create the saved admin database connection."""
        if self._session_factory is not None:
            return self._session_factory()

        from lib.config_mgr import ConfigManager
        from lib.fsutils import project_home
        from lib.session_manager import DBSession
        from lib.user_security import UserSecurity

        config_path = project_home() / "resources" / "config" / "orac.ini"
        config_mgr = ConfigManager(config_file_path=config_path)
        project_identifier = self._project_identifier or config_mgr.config_value(
            section="global",
            key="project_identifier",
            default="Orac",
        )
        user_security = UserSecurity(
            project_identifier=project_identifier,
            resource_type="dsn",
        )
        username, password, dsn = user_security.named_connection_creds(
            connection_name=self._connection_name
        )
        wallet_zip_path = user_security.connection_property(
            connection_name=self._connection_name,
            property_key="wallet_zip_path",
            default_value="",
        )
        return DBSession(
            wallet_zip_path=wallet_zip_path or "",
            verbose=False,
            user=username,
            password=password,
            dsn=dsn,
        )

    def _log_info(self, message: str) -> None:
        """Write an info message when a logger is available."""
        if self._logger and hasattr(self._logger, "log_info"):
            self._logger.log_info(message)


class DockerPluginDatabaseRunner:
    """Stages plugin database archives into the Oracle container and invokes deployment."""

    def __init__(
        self,
        *,
        container_name: str = "orac-db",
        docker_bin: str = "docker",
        container_staging_root: str = "/home/oracle/orac/plugin_staging",
        deploy_script_path: str = "/home/oracle/orac/bin/deploy-plugin-db.sh",
        deploy_script_source_path: Path | None = None,
        oracle_pdb: str = "FREEPDB1",
        command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        logger: Any | None = None,
    ) -> None:
        """Initialise the Docker-backed deployment runner.

        :param container_name: Oracle database container name.
        :param docker_bin: Docker executable.
        :param container_staging_root: Root staging directory inside container.
        :param deploy_script_path: Container-side plugin deployment script path.
        :param deploy_script_source_path: Host source for the container deploy script.
        :param oracle_pdb: Oracle pluggable database name used for state checks.
        :param command_runner: Injectable subprocess-compatible runner.
        :param logger: Optional Orac logger.
        """
        self._container_name = container_name
        self._docker_bin = docker_bin
        self._container_staging_root = container_staging_root.rstrip("/")
        self._deploy_script_path = deploy_script_path
        self._deploy_script_source_path = deploy_script_source_path or (
            Path(__file__).resolve().parents[2]
            / "resources"
            / "docker"
            / "oracle"
            / "bin"
            / "deploy-plugin-db.sh"
        )
        _validate_oracle_identifier(oracle_pdb, "oracle_pdb")
        self._oracle_pdb = oracle_pdb
        self._command_runner = command_runner or subprocess.run
        self._logger = logger

    def provision_schemas(self, manifest: PluginManifest) -> None:
        """Provision dedicated users with current-registration ownership receipts.

        Existing users require an exact receipt and dictionary incarnation.
        A crash between CREATE USER and the receipt fails closed on retry.
        """
        validate_declared_database_schemas(manifest)
        sql = _schema_provisioning_sql(manifest, oracle_pdb=self._oracle_pdb)
        command = [
            self._docker_bin,
            "exec",
            self._container_name,
            "bash",
            "-lc",
            "sqlplus -L -s / as sysdba <<'SQL'\n" + sql + "\nSQL",
        ]
        output = self._run_capture(
            command, "provision receipted plugin schemas", timeout_seconds=180
        )
        if "ORAC_PLUGIN_SCHEMA_RECEIPTS_OK" not in output:
            raise PluginDatabaseDeploymentError(
                "Plugin schema provisioning did not confirm ownership receipts."
            )

    @property
    def administrative_target(self) -> tuple[str, str]:
        """Return the host-configured container and PDB for companion cleanup."""
        return self._container_name, self._oracle_pdb

    def schema_removal_inventory(
        self,
        manifest: PluginManifest,
        *,
        plugin_registry_id: int,
        removal_id: str | None = None,
    ) -> dict[str, Any]:
        """Read dictionary-backed ownership and reject unsafe cleanup targets.

        This performs no DDL or journal writes. An incomplete removal ID allows
        inspection of an absent user after an uncertain DROP USER response.
        """
        sql = _schema_removal_sql(
            manifest,
            oracle_pdb=self._oracle_pdb,
            plugin_registry_id=plugin_registry_id,
            removal_id=removal_id,
        )
        output = self._run_schema_maintenance(sql, "inspect plugin schema ownership")
        prefix = "ORAC_PLUGIN_SCHEMA_INVENTORY:"
        records = [
            line[len(prefix) :]
            for line in output.splitlines()
            if line.startswith(prefix)
        ]
        if len(records) != 1 or len(records[0].encode("utf-8")) > 65536:
            raise PluginDatabaseDeploymentError("Schema inventory was not confirmed.")
        try:
            inventory = json.loads(records[0])
        except (ValueError, TypeError) as exc:
            raise PluginDatabaseDeploymentError(
                "Schema inventory was invalid."
            ) from exc
        if (
            not isinstance(inventory, dict)
            or inventory.get("plugin_registry_id") != plugin_registry_id
            or inventory.get("plugin_id") != manifest.plugin_id
            or not isinstance(inventory.get("database_identity"), str)
            or not inventory["database_identity"]
            or not isinstance(inventory.get("schemas"), list)
            or [
                entry.get("schema_name")
                for entry in inventory["schemas"]
                if isinstance(entry, dict)
            ]
            != [
                _schema_identifier(item.schema_name)
                for item in manifest.database_schemas
            ]
        ):
            raise PluginDatabaseDeploymentError(
                "Schema inventory identity did not match."
            )
        return inventory

    def clean_up_schemas(
        self,
        manifest: PluginManifest,
        *,
        plugin_registry_id: int,
        removal_id: str,
        database_identity: str,
        keep_schema: bool,
    ) -> None:
        """Apply an already journaled disposition after fresh dictionary checks.

        The durable operation, exact current registration, PDB identity and
        ownership receipts authorize every schema. No caller-supplied username
        is accepted. Lost replies are recovered by inspecting actual state.
        """
        sql = _schema_removal_sql(
            manifest,
            oracle_pdb=self._oracle_pdb,
            plugin_registry_id=plugin_registry_id,
            removal_id=removal_id,
            database_identity=database_identity,
            keep_schema=keep_schema,
        )
        output = self._run_schema_maintenance(sql, "clean up receipted plugin schemas")
        if "ORAC_PLUGIN_SCHEMA_CLEANUP_OK" not in output.splitlines():
            raise PluginDatabaseDeploymentError("Schema cleanup was not confirmed.")

    def _run_schema_maintenance(self, sql: str, action: str) -> str:
        """Run host-generated administrative SQL with a bounded wait."""
        command = [
            self._docker_bin,
            "exec",
            self._container_name,
            "bash",
            "-lc",
            "sqlplus -L -s / as sysdba <<'SQL'\n" + sql + "\nSQL",
        ]
        return self._run_capture(command, action, timeout_seconds=180)

    def deploy(
        self,
        *,
        manifest: PluginManifest,
        archive: PluginDatabaseArchive,
    ) -> None:
        """Stage and deploy an archive inside the Oracle database container.

        :param manifest: Plugin manifest being deployed.
        :param archive: Prepared database payload archive.
        :raises PluginDatabaseDeploymentError: when staging or deployment fails.
        """
        container_dir = (
            f"{self._container_staging_root}/{manifest.plugin_id}/{manifest.version}"
        )
        container_archive = f"{container_dir}/{archive.archive_path.name}"

        self._sync_deploy_script()
        self._run(
            [
                self._docker_bin,
                "exec",
                "-u",
                "0",
                self._container_name,
                "bash",
                "-lc",
                (
                    f"mkdir -p '{container_dir}' "
                    f"&& chown 54321:54321 '{container_dir}' "
                    f"&& chmod 750 '{container_dir}'"
                ),
            ],
            "prepare plugin database staging directory",
        )
        self._run(
            [
                self._docker_bin,
                "cp",
                str(archive.archive_path),
                f"{self._container_name}:{container_archive}",
            ],
            "copy plugin database archive",
        )
        self._run(
            [
                self._docker_bin,
                "exec",
                self._container_name,
                self._deploy_script_path,
                "--plugin-id",
                manifest.plugin_id,
                "--archive",
                container_archive,
            ],
            "deploy plugin database archive",
        )

    def _sync_deploy_script(self) -> None:
        """Copy the current container deployment helper into the DB container."""
        if not self._deploy_script_source_path.is_file():
            raise PluginDatabaseDeploymentError(
                "Plugin database deploy script source is missing: "
                f"{self._deploy_script_source_path}"
            )

        self._run(
            [
                self._docker_bin,
                "cp",
                str(self._deploy_script_source_path),
                f"{self._container_name}:{self._deploy_script_path}",
            ],
            "copy plugin database deploy script",
        )
        self._run(
            [
                self._docker_bin,
                "exec",
                "-u",
                "0",
                self._container_name,
                "bash",
                "-lc",
                (
                    f"chown 54321:54321 '{self._deploy_script_path}' "
                    f"&& chmod 750 '{self._deploy_script_path}'"
                ),
            ],
            "prepare plugin database deploy script",
        )

    def already_deployed(
        self,
        *,
        manifest: PluginManifest,
        payload_checksum: str,
    ) -> bool:
        """Return whether this payload was already successfully deployed.

        :param manifest: Plugin manifest being considered.
        :param payload_checksum: Canonical payload checksum from packaging inputs.
        :returns: ``True`` when all declared plugin schemas have succeeded rows.
        :raises PluginDatabaseDeploymentError: when the state check cannot run.
        """
        schema_names = [schema.schema_name for schema in manifest.database_schemas]
        if not schema_names:
            return False

        sql = _already_deployed_sql(
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            payload_checksum=payload_checksum,
            schema_names=schema_names,
            oracle_pdb=self._oracle_pdb,
            require_liquibase_tracking=(
                manifest.database_deployment.deployment_type == "liquibase"
            ),
        )
        command = [
            self._docker_bin,
            "exec",
            self._container_name,
            "bash",
            "-lc",
            "sqlplus -L -s / as sysdba <<'SQL'\n" + sql + "\nSQL",
        ]
        output = self._run_capture(command, "check plugin database deployment state")
        return "ORAC_PLUGIN_DB_ALREADY_DEPLOYED=Y" in output

    def payload_objects_deployed(
        self,
        *,
        manifest: PluginManifest,
        schema_payload_path: Path,
    ) -> bool:
        """Return whether expected payload objects and grants are present."""
        expected = expected_deployment_objects(
            manifest=manifest,
            schema_payload_path=schema_payload_path,
        )
        if not expected["objects"] and not expected["grants"]:
            return True

        sql = _payload_objects_deployed_sql(
            expected=expected,
            oracle_pdb=self._oracle_pdb,
        )
        command = [
            self._docker_bin,
            "exec",
            self._container_name,
            "bash",
            "-lc",
            "sqlplus -L -s / as sysdba <<'SQL'\n" + sql + "\nSQL",
        ]
        output = self._run_capture(command, "verify plugin database payload objects")
        return "ORAC_PLUGIN_DB_PAYLOAD_OBJECTS_DEPLOYED=Y" in output

    def mark_payload_deployed(
        self,
        *,
        manifest: PluginManifest,
        payload_checksum: str,
        log_path: str = "verified_existing_payload_objects",
    ) -> None:
        """Record an already-present payload as deployed for the current checksum.

        :param manifest: Plugin manifest being considered.
        :param payload_checksum: Canonical payload checksum from packaging inputs.
        :param log_path: Diagnostic marker stored with the deployment state row.
        :raises PluginDatabaseDeploymentError: when the state update cannot run.
        """
        schema_names = [schema.schema_name for schema in manifest.database_schemas]
        if not schema_names:
            return

        sql = _mark_payload_deployed_sql(
            plugin_id=manifest.plugin_id,
            plugin_version=manifest.version,
            payload_checksum=payload_checksum,
            schema_names=schema_names,
            oracle_pdb=self._oracle_pdb,
            log_path=log_path,
        )
        command = [
            self._docker_bin,
            "exec",
            self._container_name,
            "bash",
            "-lc",
            "sqlplus -L -s / as sysdba <<'SQL'\n" + sql + "\nSQL",
        ]
        self._run_capture(command, "record verified plugin database deployment")

    def _run(self, command: list[str], action: str) -> None:
        """Run one Docker command and raise a sanitized deployment error."""
        self._run_capture(command, action)

    def _run_capture(
        self, command: list[str], action: str, *, timeout_seconds: int | None = None
    ) -> str:
        """Run one Docker command and return combined output."""
        timeout_options: dict[str, Any] = (
            {"timeout": timeout_seconds} if timeout_seconds is not None else {}
        )
        try:
            completed = self._command_runner(
                command,
                check=False,
                text=True,
                capture_output=True,
                **timeout_options,
            )
        except subprocess.TimeoutExpired as exc:
            raise PluginDatabaseDeploymentError(
                f"Timed out while attempting to {action}; verify actual state before retry."
            ) from exc
        except OSError as exc:
            raise PluginDatabaseDeploymentError(f"Unable to {action}: {exc}") from exc

        if completed.returncode != 0:
            output = "\n".join(
                part.strip()
                for part in (completed.stdout, completed.stderr)
                if part and part.strip()
            )
            raise PluginDatabaseDeploymentError(
                f"Failed to {action}: exit={completed.returncode}; {output}"
            )
        output = "\n".join(
            part.strip()
            for part in (completed.stdout, completed.stderr)
            if part and part.strip()
        )
        if output:
            self._log_debug(f"Plugin database {action} output:\n{output}")
        return output

    def _log_debug(self, message: str) -> None:
        """Write a debug message when a logger is available."""
        if self._logger and hasattr(self._logger, "log_debug"):
            self._logger.log_debug(message)


class DockerPluginLiquibaseDatabaseRunner(DockerPluginDatabaseRunner):
    """Stages plugin archives and invokes isolated plugin Liquibase deployment."""

    def __init__(
        self,
        *,
        container_name: str = "orac-db",
        docker_bin: str = "docker",
        container_staging_root: str = "/home/oracle/orac/plugin_staging",
        deploy_script_path: str = "/home/oracle/orac/bin/deploy-plugin-liquibase-db.sh",
        deploy_script_source_path: Path | None = None,
        oracle_pdb: str = "FREEPDB1",
        command_runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        logger: Any | None = None,
    ) -> None:
        super().__init__(
            container_name=container_name,
            docker_bin=docker_bin,
            container_staging_root=container_staging_root,
            deploy_script_path=deploy_script_path,
            deploy_script_source_path=deploy_script_source_path
            or (
                Path(__file__).resolve().parents[2]
                / "resources"
                / "docker"
                / "oracle"
                / "bin"
                / "deploy-plugin-liquibase-db.sh"
            ),
            oracle_pdb=oracle_pdb,
            command_runner=command_runner,
            logger=logger,
        )

    def deploy(
        self,
        *,
        manifest: PluginManifest,
        archive: PluginDatabaseArchive,
    ) -> None:
        """Stage and deploy an archive once for each declared plugin schema."""
        container_dir = (
            f"{self._container_staging_root}/{manifest.plugin_id}/{manifest.version}"
        )
        container_archive = f"{container_dir}/{archive.archive_path.name}"
        controller = manifest.database_deployment.controller or (
            "db/liquibase/pluginController.xml"
        )

        self._sync_deploy_script()
        self._run(
            [
                self._docker_bin,
                "exec",
                "-u",
                "0",
                self._container_name,
                "bash",
                "-lc",
                (
                    f"mkdir -p '{container_dir}' "
                    f"&& chown 54321:54321 '{container_dir}' "
                    f"&& chmod 750 '{container_dir}'"
                ),
            ],
            "prepare plugin Liquibase staging directory",
        )
        self._run(
            [
                self._docker_bin,
                "cp",
                str(archive.archive_path),
                f"{self._container_name}:{container_archive}",
            ],
            "copy plugin Liquibase database archive",
        )
        for schema in manifest.database_schemas:
            schema_name = schema.schema_name.upper()
            self._run(
                [
                    self._docker_bin,
                    "exec",
                    self._container_name,
                    self._deploy_script_path,
                    "--plugin-id",
                    manifest.plugin_id,
                    "--archive",
                    container_archive,
                    "--schema-name",
                    schema_name,
                    "--default-schema-name",
                    schema_name,
                    "--liquibase-schema-name",
                    schema_name,
                    "--controller",
                    controller,
                ],
                f"deploy plugin Liquibase archive for {schema_name}",
            )


class PluginDatabaseDeployer:
    """Validates, packages, and deploys plugin-owned database schema payloads."""

    def __init__(
        self,
        *,
        runner: DockerPluginDatabaseRunner | None = None,
        liquibase_runner: DockerPluginLiquibaseDatabaseRunner | None = None,
        schema_provisioner: PluginDatabaseSchemaProvisioner | None = None,
        archive_root: Path | None = None,
        clock: Callable[[], datetime] | None = None,
        logger: Any | None = None,
    ) -> None:
        """Create a deployer.

        :param runner: Container deployment runner.
        :param schema_provisioner: Plugin schema owner provisioner.
        :param archive_root: Host archive output root; defaults to a temp tree.
        :param clock: Injectable timestamp provider.
        :param logger: Optional Orac logger.
        """
        self._logger = logger
        self._runner = runner or DockerPluginDatabaseRunner(logger=logger)
        self._liquibase_runner = (
            liquibase_runner or DockerPluginLiquibaseDatabaseRunner(logger=logger)
        )
        self._schema_provisioner = schema_provisioner
        self._archive_root = (
            Path(archive_root)
            if archive_root
            else Path(tempfile.gettempdir()) / "orac-plugin-db"
        )
        self._clock = clock or (lambda: datetime.now(UTC))

    def deploy_if_needed(
        self, manifest: PluginManifest
    ) -> PluginDatabaseDeploymentResult:
        """Deploy a plugin database payload when required by the manifest.

        :param manifest: Plugin manifest to evaluate.
        :returns: Deployment/eligibility result.
        """
        if not manifest.database_schemas:
            return PluginDatabaseDeploymentResult(
                plugin_id=manifest.plugin_id,
                status="not_required",
                eligible=True,
                message="Plugin does not require database deployment.",
            )

        schema_payload_path = plugin_schema_payload_path(manifest)
        schema_names = ", ".join(
            schema.schema_name for schema in manifest.database_schemas
        )
        self._log_info(
            "Plugin database deployment check starting for "
            f"'{manifest.plugin_id}' schemas [{schema_names}]."
        )
        if not schema_payload_path.is_dir():
            if not manifest.database_required:
                self._log_warning(
                    "Optional plugin database payload is missing for "
                    f"'{manifest.plugin_id}': {schema_payload_path}"
                )
                return PluginDatabaseDeploymentResult(
                    plugin_id=manifest.plugin_id,
                    status="optional_missing",
                    eligible=True,
                    message=(
                        "Optional plugin database payload is missing; plugin remains eligible."
                    ),
                )
            return self._disabled_result(
                manifest,
                "missing_disabled",
                f"Required plugin database payload is missing: {schema_payload_path}",
            )

        try:
            self._log_info(
                f"Validating plugin database payload for '{manifest.plugin_id}'."
            )
            validate_declared_database_schemas(manifest)
            validate_schema_payload(schema_payload_path, manifest=manifest)
            payload_checksum = calculate_payload_checksum(manifest)
            self._log_info(
                "Plugin database payload validated for "
                f"'{manifest.plugin_id}' checksum={payload_checksum}."
            )
            self._log_info(
                "Provisioning plugin database schemas or reconciling grants for "
                f"'{manifest.plugin_id}'."
            )
            provisioner = self._schema_provisioner or PluginDatabaseSchemaProvisioner(
                admin_runner=self._runner_for_manifest(manifest), logger=self._logger
            )
            provisioner.ensure_schemas(manifest)
            if self._is_already_deployed(
                manifest,
                payload_checksum,
                schema_payload_path,
            ):
                self._log_info(
                    "Plugin database payload already deployed for "
                    f"'{manifest.plugin_id}' checksum={payload_checksum}; skipping."
                )
                return PluginDatabaseDeploymentResult(
                    plugin_id=manifest.plugin_id,
                    status="already_deployed",
                    eligible=True,
                    message="Plugin database payload already deployed.",
                    payload_checksum=payload_checksum,
                )
            self._log_info(
                f"Packaging plugin database payload for '{manifest.plugin_id}'."
            )
            archive = self.create_archive(manifest)
            self._log_info(
                "Staging and deploying plugin database archive for "
                f"'{manifest.plugin_id}': {archive.archive_path}"
            )
            runner = self._runner_for_manifest(manifest)
            runner.deploy(manifest=manifest, archive=archive)
            if not self._is_already_deployed(
                manifest,
                archive.payload_checksum,
                schema_payload_path,
            ):
                raise PluginDatabaseDeploymentError(
                    "Plugin database deployment completed but final ledger, "
                    "tracking, object, or grant verification failed for "
                    f"'{manifest.plugin_id}'."
                )
        except PluginDatabaseValidationError as exc:
            self._log_warning(
                "Plugin database validation failed for "
                f"'{manifest.plugin_id}': {exc}"
            )
            return self._disabled_result(
                manifest,
                "validation_failed",
                str(exc),
            )
        except PluginDatabaseDeploymentError as exc:
            self._log_warning(
                "Plugin database deployment failed for "
                f"'{manifest.plugin_id}': {exc}"
            )
            if not manifest.database_required:
                return PluginDatabaseDeploymentResult(
                    plugin_id=manifest.plugin_id,
                    status="deployment_failed",
                    eligible=True,
                    message=(
                        "Optional plugin database deployment failed; plugin remains eligible: "
                        f"{exc}"
                    ),
                )
            return self._disabled_result(
                manifest,
                "deployment_failed",
                str(exc),
            )

        return PluginDatabaseDeploymentResult(
            plugin_id=manifest.plugin_id,
            status="deployed",
            eligible=True,
            message="Plugin database payload deployed successfully.",
            archive_path=archive.archive_path,
            payload_checksum=archive.payload_checksum,
            archive_checksum=archive.archive_checksum,
        )

    def create_archive(self, manifest: PluginManifest) -> PluginDatabaseArchive:
        """Create a deterministic tar.gz archive for a plugin database payload.

        :param manifest: Plugin manifest whose payload should be packaged.
        :raises PluginDatabaseDeploymentError: when validation or packaging fails.
        """
        schema_payload_path = plugin_schema_payload_path(manifest)
        if not schema_payload_path.is_dir():
            raise PluginDatabaseDeploymentError(
                f"Required plugin database payload is missing: {schema_payload_path}"
            )

        validate_declared_database_schemas(manifest)
        validate_schema_payload(schema_payload_path, manifest=manifest)

        self._archive_root.mkdir(parents=True, exist_ok=True)
        output_dir = self._archive_root / manifest.plugin_id / manifest.version
        output_dir.mkdir(parents=True, exist_ok=True)
        archive_path = output_dir / f"{manifest.plugin_id}-{manifest.version}-db.tar.gz"
        created_timestamp = (
            self._clock().astimezone(UTC).replace(microsecond=0).isoformat()
        )

        files = _archive_inputs(manifest)
        payload_checksum = _payload_checksum(files, manifest)
        archive_manifest = _archive_manifest(
            manifest=manifest,
            created_timestamp=created_timestamp,
            payload_checksum=payload_checksum,
        )

        with archive_path.open("wb") as archive_file:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=archive_file,
                compresslevel=9,
                mtime=0,
            ) as gzip_file:
                with tarfile.open(fileobj=gzip_file, mode="w") as tar:
                    _add_bytes_to_tar(
                        tar,
                        "manifest.json",
                        json.dumps(archive_manifest, indent=2, sort_keys=True).encode(
                            "utf-8"
                        )
                        + b"\n",
                    )
                    for source_path, archive_name in files:
                        _add_file_to_tar(tar, source_path, archive_name)

        archive_checksum = _sha256_file(archive_path)
        return PluginDatabaseArchive(
            archive_path=archive_path,
            payload_checksum=payload_checksum,
            archive_checksum=archive_checksum,
            manifest=archive_manifest,
        )

    def _runner_for_manifest(
        self, manifest: PluginManifest
    ) -> DockerPluginDatabaseRunner:
        """Return the deployment runner for the manifest's declared mechanism."""
        if manifest.database_deployment.deployment_type == "liquibase":
            return self._liquibase_runner
        return self._runner

    def administrative_runner_for(
        self, manifest: PluginManifest
    ) -> DockerPluginDatabaseRunner:
        """Use the same host target for provisioning, inspection and removal."""
        return self._runner_for_manifest(manifest)

    @staticmethod
    def _disabled_result(
        manifest: PluginManifest,
        status: Literal["missing_disabled", "validation_failed", "deployment_failed"],
        message: str,
    ) -> PluginDatabaseDeploymentResult:
        return PluginDatabaseDeploymentResult(
            plugin_id=manifest.plugin_id,
            status=status,
            eligible=False,
            message=message,
        )

    def _is_already_deployed(
        self,
        manifest: PluginManifest,
        payload_checksum: str,
        schema_payload_path: Path,
    ) -> bool:
        """Return whether state and expected objects confirm deployment."""
        runner = self._runner_for_manifest(manifest)
        checker = getattr(runner, "already_deployed", None)
        state_says_deployed = False
        try:
            if checker is not None:
                state_says_deployed = bool(
                    checker(
                        manifest=manifest,
                        payload_checksum=payload_checksum,
                    )
                )
        except PluginDatabaseDeploymentError:
            self._log_warning(
                "Plugin database deployment state check failed for "
                f"'{manifest.plugin_id}'; verifying live payload objects before "
                "deciding whether to redeploy."
            )

        object_checker = getattr(runner, "payload_objects_deployed", None)
        if object_checker is None:
            return state_says_deployed

        expected = expected_deployment_objects(
            manifest=manifest,
            schema_payload_path=schema_payload_path,
        )
        has_verifiable_payload = bool(expected["objects"] or expected["grants"])
        if not state_says_deployed and not has_verifiable_payload:
            return False
        if (
            not state_says_deployed
            and manifest.database_deployment.deployment_type == "liquibase"
        ):
            self._log_warning(
                "Plugin Liquibase payload for "
                f"'{manifest.plugin_id}' has no recorded successful deployment "
                "for the current checksum; running Liquibase update so changed "
                "runOnChange objects are applied."
            )
            return False

        try:
            objects_present = bool(
                object_checker(
                    manifest=manifest,
                    schema_payload_path=schema_payload_path,
                )
            )
            if not objects_present:
                self._log_warning(
                    "Plugin database deployment state says "
                    f"'{manifest.plugin_id}' is deployed, but expected payload "
                    "objects or grants are missing; redeploying."
                )
                return False
            if not state_says_deployed:
                self._log_warning(
                    "Plugin database payload objects and grants already exist for "
                    f"'{manifest.plugin_id}', but the current checksum was not "
                    "recorded; recording verified deployment and skipping DDL."
                )
                marker = getattr(runner, "mark_payload_deployed", None)
                if marker is not None:
                    try:
                        marker(
                            manifest=manifest,
                            payload_checksum=payload_checksum,
                        )
                    except PluginDatabaseDeploymentError as exc:
                        self._log_warning(
                            "Unable to record verified plugin database deployment "
                            f"for '{manifest.plugin_id}': {exc}"
                        )
            return objects_present
        except PluginDatabaseDeploymentError:
            self._log_warning(
                "Plugin database live object check failed for "
                f"'{manifest.plugin_id}'; continuing with deployment attempt."
            )
            return False

    def _log_info(self, message: str) -> None:
        """Write an info message when a logger is available."""
        if self._logger and hasattr(self._logger, "log_info"):
            self._logger.log_info(message)

    def _log_warning(self, message: str) -> None:
        """Write a warning message when a logger is available."""
        if self._logger and hasattr(self._logger, "log_warning"):
            self._logger.log_warning(message)


def _schema_removal_sql(
    manifest: PluginManifest,
    *,
    oracle_pdb: str,
    plugin_registry_id: int,
    removal_id: str | None = None,
    database_identity: str | None = None,
    keep_schema: bool | None = None,
) -> str:
    """Build fail-closed inspection or cleanup for manifest-declared schemas.

    Cleanup additionally requires the durable operation's immutable inventory.
    Dictionary queries deliberately reject unmanaged autonomous resources;
    v1 does not guess how to stop or transfer them.
    """
    validate_declared_database_schemas(manifest)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", manifest.plugin_id):
        raise PluginDatabaseValidationError(
            "Invalid plugin identity for schema cleanup."
        )
    if type(plugin_registry_id) is not int or plugin_registry_id <= 0:
        raise PluginDatabaseValidationError("A current registration ID is required.")
    if removal_id is not None and not re.fullmatch(r"[a-fA-F0-9]{32}", removal_id):
        raise PluginDatabaseValidationError("Invalid removal operation ID.")
    mutate = keep_schema is not None
    if mutate and (
        not removal_id or not database_identity or type(keep_schema) is not bool
    ):
        raise PluginDatabaseValidationError(
            "Cleanup requires durable removal authorization."
        )
    if database_identity is not None and (
        len(database_identity) > 256
        or "\n" in database_identity
        or "\r" in database_identity
    ):
        raise PluginDatabaseValidationError("Invalid database identity.")
    pdb = _schema_identifier(oracle_pdb)
    plugin = _sql_literal(manifest.plugin_id)
    operation = _sql_literal(removal_id) if removal_id else "null"
    expected_database = _sql_literal(database_identity) if database_identity else "null"
    disposition = "RETAINED" if keep_schema else "DROPPED"
    statements: list[str] = []
    for schema in manifest.database_schemas:
        name = _schema_identifier(schema.schema_name)
        if name in {"SYS", "SYSTEM", "PDBADMIN", "PUBLIC"} or name.startswith(
            ("C##", "APEX_", "FLOWS_", "ORDS_")
        ):
            raise PluginDatabaseValidationError("Protected schema cannot be removed.")
        bridge_conditions = ["1 = 0"]
        for dependency_id in schema.bridge_api_dependencies:
            dependency = PLUGIN_BRIDGE_API_CATALOG[dependency_id]
            bridge_conditions.append(
                f"(owner = '{dependency['owner']}' and table_name = '{dependency['object_name']}' "
                f"and privilege = '{dependency['privilege']}' and grantable = 'NO')"
            )
        cleanup = ""
        if mutate:
            cleanup = f"""
  select count(*) into l_count
    from json_table(l_operation.resource_inventory, '$.database.schemas[*]'
      columns (receipt_id number path '$.receipt_id',
               schema_name varchar2(128) path '$.schema_name')) inventory
   where inventory.receipt_id = l_receipt.schema_ownership_id
     and inventory.schema_name = '{name}';
  if l_count <> 1 then
    raise_application_error(-20079, 'Schema receipt is absent from authorized inventory.');
  end if;
  if l_present = 1 and l_receipt.disposition = 'OWNED' then
    -- Every DDL commits implicitly. Revalidate incarnation before each call.
    assert_incarnation('{name}', l_receipt);
    execute immediate 'alter user {name} account lock';
    assert_resources('{name}');
    for item in (select grantee, table_name, privilege from dba_tab_privs
                  where owner = '{name}' and grantee <> '{name}') loop
      assert_incarnation('{name}', l_receipt);
      execute immediate 'revoke ' || item.privilege || ' on {name}.' ||
        dbms_assert.enquote_name(item.table_name, false) || ' from ' ||
        dbms_assert.enquote_name(item.grantee, false);
    end loop;
    for item in (select owner, table_name, privilege from dba_tab_privs
                  where grantee = '{name}' and owner <> '{name}') loop
      assert_incarnation('{name}', l_receipt);
      execute immediate 'revoke ' || item.privilege || ' on ' ||
        dbms_assert.enquote_name(item.owner, false) || '.' ||
        dbms_assert.enquote_name(item.table_name, false) || ' from {name}';
    end loop;
    {"" if not keep_schema else f'''for item in (select privilege from dba_sys_privs where grantee = '{name}') loop
      assert_incarnation('{name}', l_receipt);
      execute immediate 'revoke ' || item.privilege || ' from {name}';
    end loop;'''}
    assert_incarnation('{name}', l_receipt);
    assert_resources('{name}');
    {f"execute immediate 'alter user {name} quota 0 on users';" if keep_schema else f"execute immediate 'drop user {name} cascade';"}
  end if;
  orac_api.plugin_schema_ownership_tapi.record_disposition(
    l_receipt.schema_ownership_id, {operation}, '{disposition}');
  commit;
"""
        statements.append(f"""
  select count(*) into l_count
    from orac_api.plugin_registry_v registry,
         json_table(registry.database_schemas_summary, '$[*]'
           columns (schema_name varchar2(128) path '$')) declared
   where registry.plugin_registry_id = {plugin_registry_id}
     and upper(declared.schema_name) = '{name}';
  if l_count <> 1 then
    raise_application_error(-20079, 'Schema differs from current registration.');
  end if;
  select count(*) into l_count from orac_api.plugin_schema_ownership_v
   where plugin_registry_id = {plugin_registry_id} and plugin_id = {plugin}
     and schema_name = '{name}';
  if l_count = 0 then
    select count(*) into l_present from dba_users where username = '{name}';
    if l_present <> 0 then
      raise_application_error(-20079, 'Unreceipted existing schema cannot be adopted or removed.');
    end if;
    {f'''select count(*) into l_count
      from json_table(l_operation.resource_inventory, '$.database.schemas[*]'
        columns (schema_name varchar2(128) path '$.schema_name',
                 state varchar2(32) path '$.state')) inventory
     where schema_name = '{name}' and state = 'NOT_PROVISIONED';
    if l_count <> 1 then
      raise_application_error(-20079, 'Unprovisioned schema differs from authorized inventory.');
    end if;''' if mutate else ''}
    l_item := json_object_t();
    l_item.put('schema_name', '{name}');
    l_item.put('state', 'NOT_PROVISIONED');
    l_item.put('present', 0);
    l_item.put_null('receipt_id');
    l_schemas.append(l_item);
  else
  select * into l_receipt from orac_api.plugin_schema_ownership_v
   where plugin_registry_id = {plugin_registry_id} and plugin_id = {plugin}
     and database_identity = l_database_identity and schema_name = '{name}'
     and (disposition = 'OWNED' or removal_id = {operation});
  select count(*) into l_present from dba_users where username = '{name}';
  if l_present = 1 then
    if l_receipt.disposition = 'DROPPED' then
      raise_application_error(-20079, 'A removed schema name is occupied again.');
    end if;
    assert_incarnation('{name}', l_receipt);
    assert_resources('{name}');
    if l_receipt.disposition = 'RETAINED' then
      select count(*) into l_count from dba_users
       where username = '{name}' and account_status like '%LOCKED%';
      if l_count <> 1 then
        raise_application_error(-20079, 'Retained schema is no longer locked.');
      end if;
      select sum(grants_count) into l_count from (
        select count(*) grants_count from dba_tab_privs
         where owner = '{name}' or grantee = '{name}'
        union all select count(*) from dba_sys_privs where grantee = '{name}'
      );
      if l_count <> 0 then
        raise_application_error(-20079, 'Retained schema has been reconnected.');
      end if;
    end if;
    select count(*) into l_count from dba_tab_privs
     where grantee = '{name}' and owner <> '{name}'
       and not ({' or '.join(bridge_conditions)});
    if l_count <> 0 then
      raise_application_error(-20079, 'Unexpected incoming object grants block cleanup.');
    end if;
  elsif {operation} is null or l_operation.schema_disposition <> 'DROP'
        or l_receipt.disposition = 'RETAINED' then
    raise_application_error(-20079, 'Missing schema requires an authorized DROP recovery.');
  end if;
  l_item := json_object_t();
  l_item.put('schema_name', '{name}');
  l_item.put('receipt_id', l_receipt.schema_ownership_id);
  l_item.put('database_user_id', l_receipt.database_user_id);
  l_item.put('database_user_created_on', to_char(l_receipt.database_user_created_on, 'YYYY-MM-DD"T"HH24:MI:SS'));
  l_item.put('disposition', l_receipt.disposition);
  l_item.put('present', l_present);
  l_schemas.append(l_item);
  {cleanup}
  end if;
""")
    allowed_privileges = ", ".join(
        _sql_literal(item.upper())
        for item in PluginDatabaseSchemaProvisioner._SCHEMA_GRANTS
    )
    approved_extra_privileges = (
        " or ".join(
            f"(p_name = {_sql_literal(schema_name)} and privilege = {_sql_literal(privilege.upper())})"
            for (
                plugin_id,
                schema_name,
            ), privileges in _PLUGIN_SCHEMA_EXTRA_PRIVILEGES.items()
            if plugin_id == manifest.plugin_id
            for privilege in privileges
        )
        or "1 = 0"
    )
    return f"""whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off echo off feedback off serveroutput on size unlimited linesize 32767
alter session set container = {pdb};
set serveroutput on size unlimited
declare
  l_database_identity varchar2(256 char);
  l_count number;
  l_present number;
  l_receipt orac_api.plugin_schema_ownership_v%rowtype;
  l_operation orac_api.plugin_removals_v%rowtype;
  l_result json_object_t := json_object_t();
  l_schemas json_array_t := json_array_t();
  l_deployments json_array_t := json_array_t();
  l_item json_object_t;

  procedure assert_incarnation(p_name varchar2,
    p_receipt orac_api.plugin_schema_ownership_v%rowtype) is
    l_matches number;
  begin
    select count(*) into l_matches from dba_users
     where username = p_name and user_id = p_receipt.database_user_id
       and created = p_receipt.database_user_created_on
       and oracle_maintained = 'N' and common = 'NO';
    if l_matches <> 1 then
      raise_application_error(-20079, 'Schema ownership incarnation changed.');
    end if;
  end;

  procedure assert_resources(p_name varchar2) is
    l_blockers number;
  begin
    select sum(blockers) into l_blockers from (
      select count(*) blockers from gv$session where username = p_name
      union all select count(*) from dba_constraints c join dba_constraints parent
        on parent.owner = c.r_owner and parent.constraint_name = c.r_constraint_name
        where c.constraint_type = 'R' and parent.owner = p_name and c.owner <> p_name
      union all select count(*) from dba_dependencies
        where referenced_owner = p_name and owner <> p_name
      union all select count(*) from dba_synonyms
        where table_owner = p_name and owner <> p_name
      union all select count(*) from dba_scheduler_jobs where owner = p_name
      union all select count(*) from dba_scheduler_programs where owner = p_name
      union all select count(*) from dba_scheduler_schedules where owner = p_name
      union all select count(*) from dba_jobs where schema_user = p_name or log_user = p_name
      union all select count(*) from dba_queue_tables where owner = p_name
      union all select count(*) from dba_db_links where owner = p_name
      union all select count(*) from dba_host_aces where principal = p_name
      union all select count(*) from dba_wallet_aces where principal = p_name
      union all select count(*) from dba_proxies where proxy = p_name or client = p_name
      union all select count(*) from dba_role_privs where grantee = p_name
      union all select count(*) from dba_sys_privs where grantee = p_name
        and ((privilege not in ({allowed_privileges}) and not ({approved_extra_privileges}))
             or admin_option <> 'NO')
      union all select count(*) from dba_col_privs where owner = p_name or grantee = p_name
      union all select count(*) from dba_tab_privs where owner = p_name and grantee <> p_name
        and (grantee not in ('ORAC_PLUGIN', 'ORAC_APX_PUB') or grantable <> 'NO'
             or privilege not in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'EXECUTE', 'REFERENCES', 'READ'))
    );
    if l_blockers <> 0 then
      raise_application_error(-20079, 'Sessions, dependencies or unmanaged resources block schema cleanup.');
    end if;
  end;
begin
  if sys_context('userenv', 'session_user') <> 'SYS' then
    raise_application_error(-20078, 'Privileged host cleanup is required.');
  end if;
  select to_char(dbid) || ':' || rawtohex(guid) || ':' || name
    into l_database_identity from v$pdbs
   where con_id = to_number(sys_context('userenv', 'con_id'))
     and name = '{pdb}' and open_mode = 'READ WRITE';
  if {expected_database} is not null and l_database_identity <> {expected_database} then
    raise_application_error(-20079, 'Database identity changed.');
  end if;
  select count(*) into l_count from orac_code.plugin_registry_v
   where plugin_id = {plugin} and plugin_registry_id = {plugin_registry_id}
     and (removal_id is null and {operation} is null or removal_id = {operation});
  if l_count <> 1 then
    raise_application_error(-20079, 'Current registration or removal fence changed.');
  end if;
  select count(*) into l_count
    from orac_api.plugin_registry_v registry,
         json_table(registry.database_schemas_summary, '$[*]'
           columns (schema_name varchar2(128) path '$')) declared
   where registry.plugin_registry_id = {plugin_registry_id};
  if l_count <> {len(manifest.database_schemas)} then
    raise_application_error(-20079, 'Declared schema inventory changed.');
  end if;
  if {operation} is not null then
    select * into l_operation from orac_api.plugin_removals_v
     where removal_id = {operation} and plugin_id = {plugin}
       and plugin_registry_id = {plugin_registry_id}
       and database_identity = l_database_identity and completed_on is null;
    {f'''if l_operation.schema_disposition <> '{"KEEP" if keep_schema else "DROP"}' then
      raise_application_error(-20079, 'Schema disposition differs from authorization.');
    end if;''' if mutate else ''}
  end if;
  {chr(10).join(statements)}
  l_result.put('plugin_id', {plugin});
  l_result.put('plugin_registry_id', {plugin_registry_id});
  l_result.put('database_identity', l_database_identity);
  l_result.put('schemas', l_schemas);
  for deployment in (
    select schema_name, plugin_version, deployment_checksum, deployment_status
      from orac_api.plugin_db_deployments_v where plugin_id = {plugin}
     order by plugin_db_deployment_id
  ) loop
    l_item := json_object_t();
    l_item.put('schema_name', deployment.schema_name);
    l_item.put('plugin_version', deployment.plugin_version);
    l_item.put('deployment_checksum', deployment.deployment_checksum);
    l_item.put('deployment_status', deployment.deployment_status);
    l_deployments.append(l_item);
  end loop;
  l_result.put('deployments', l_deployments);
  dbms_output.put_line('ORAC_PLUGIN_SCHEMA_INVENTORY:' || l_result.to_string());
end;
/
{"prompt ORAC_PLUGIN_SCHEMA_CLEANUP_OK" if mutate else ""}
exit success
"""


def _schema_provisioning_sql(manifest: PluginManifest, *, oracle_pdb: str) -> str:
    """Wrap receipt-guarded provisioning blocks in the administrative runner."""
    pdb = _schema_identifier(oracle_pdb)
    blocks = _schema_provisioning_blocks(manifest, oracle_pdb=pdb)
    return "\n".join(
        [
            "whenever sqlerror exit failure rollback",
            "whenever oserror exit failure rollback",
            "set define off echo off feedback off serveroutput on",
            f"alter session set container = {pdb};",
            "set serveroutput on size unlimited",
            *[block + "\n/" for block in blocks],
            "prompt ORAC_PLUGIN_SCHEMA_RECEIPTS_OK",
            "exit success",
        ]
    )


def _schema_provisioning_blocks(
    manifest: PluginManifest, *, oracle_pdb: str
) -> list[str]:
    """Build administrative provisioning with dictionary-backed ownership.

    The only identifiers come from a validated manifest and the host bridge
    catalogue. The password is generated inside Oracle and is never returned.
    """
    validate_declared_database_schemas(manifest)
    validate_plugin_bridge_api_catalog()
    pdb = _schema_identifier(oracle_pdb)
    plugin = _sql_literal(manifest.plugin_id)
    blocks: list[str] = []
    for schema in manifest.database_schemas:
        name = _schema_identifier(schema.schema_name)
        if name in {"SYS", "SYSTEM", "PDBADMIN", "PUBLIC"} or name.startswith(
            ("C##", "APEX_", "FLOWS_", "ORDS_")
        ):
            raise PluginDatabaseValidationError(
                "Protected schema cannot be plugin-owned."
            )
        grants = [
            f"execute immediate 'alter user {name} quota unlimited on users';",
            *[
                f"execute immediate 'grant {privilege} to {name}';"
                for privilege in (
                    *PluginDatabaseSchemaProvisioner._SCHEMA_GRANTS,
                    *_PLUGIN_SCHEMA_EXTRA_PRIVILEGES.get(
                        (manifest.plugin_id, name), ()
                    ),
                )
            ],
        ]
        for dependency_id in schema.bridge_api_dependencies:
            dependency = PLUGIN_BRIDGE_API_CATALOG[dependency_id]
            owner = dependency["owner"]
            object_name = dependency["object_name"]
            object_type = dependency["object_type"]
            grants.append(f"""
  select count(*) into l_count from dba_objects
   where owner = '{owner}' and object_name = '{object_name}'
     and object_type = '{object_type}' and status = 'VALID';
  if l_count <> 1 then
    raise_application_error(-20079, 'Required host bridge is missing or invalid.');
  end if;
  execute immediate 'grant {dependency['privilege']} on {owner}.{object_name} to {name}';
""")
        blocks.append(f"""
declare
  l_registry_id number;
  l_database_identity varchar2(256 char);
  l_user_id number;
  l_created date;
  l_count number;
  l_receipt orac_api.plugin_schema_ownership_v%rowtype;
begin
  if sys_context('userenv', 'session_user') <> 'SYS' then
    raise_application_error(-20078, 'Privileged host provisioning is required.');
  end if;
  select to_char(dbid) || ':' || rawtohex(guid) || ':' || name
    into l_database_identity from v$pdbs
   where con_id = to_number(sys_context('userenv', 'con_id'))
     and name = '{pdb}' and open_mode = 'READ WRITE';
  select plugin_registry_id into l_registry_id
    from orac_code.plugin_registry_v
   where plugin_id = {plugin} and removal_id is null;
  select count(*) into l_count
    from orac_api.plugin_registry_v registry,
         json_table(registry.database_schemas_summary, '$[*]'
           columns (schema_name varchar2(128) path '$')) declared
   where registry.plugin_registry_id = l_registry_id
     and upper(declared.schema_name) = '{name}';
  if l_count <> 1 then
    raise_application_error(-20079, 'Current registration does not declare this schema.');
  end if;
  select count(*) into l_count from dba_users where username = '{name}';
  if l_count = 0 then
    select count(*) into l_count from orac_api.plugin_schema_ownership_v
     where database_identity = l_database_identity and schema_name = '{name}'
       and disposition in ('OWNED', 'RETAINED');
    if l_count <> 0 then
      raise_application_error(-20079, 'Missing owned or retained schema requires recovery.');
    end if;
    execute immediate 'create user {name} identified by "' ||
      dbms_random.string('x', 40) || '" default tablespace users temporary tablespace temp account lock';
    select user_id, created into l_user_id, l_created from dba_users
     where username = '{name}' and oracle_maintained = 'N' and common = 'NO';
    l_receipt.plugin_id := {plugin};
    l_receipt.plugin_registry_id := l_registry_id;
    l_receipt.database_identity := l_database_identity;
    l_receipt.schema_name := '{name}';
    l_receipt.database_user_id := l_user_id;
    l_receipt.database_user_created_on := l_created;
    select json_object('method' value 'HOST_CREATE_USER',
                       'actor' value 'SYS',
                       'schema' value '{name}' returning json)
      into l_receipt.provisioning_evidence from dual;
    orac_api.plugin_schema_ownership_tapi.ins(l_receipt);
    commit;
  else
    select user_id, created into l_user_id, l_created from dba_users
     where username = '{name}' and oracle_maintained = 'N' and common = 'NO';
    select count(*) into l_count from orac_api.plugin_schema_ownership_v
     where plugin_id = {plugin} and plugin_registry_id = l_registry_id
       and database_identity = l_database_identity and schema_name = '{name}'
       and database_user_id = l_user_id and database_user_created_on = l_created
       and disposition = 'OWNED';
    if l_count <> 1 then
      raise_application_error(-20079, 'Existing schema has no matching current ownership receipt.');
    end if;
  end if;
  {chr(10).join(grants)}
end;
""")
    return blocks


def plugin_schema_payload_path(manifest: PluginManifest) -> Path:
    """Return the plugin-local database schema payload path."""
    return manifest.plugin_dir / "db" / "schema"


def plugin_liquibase_controller_path(manifest: PluginManifest) -> Path:
    """Return the plugin-local Liquibase controller path."""
    controller = manifest.database_deployment.controller or (
        "db/liquibase/pluginController.xml"
    )
    return manifest.plugin_dir / controller


def calculate_payload_checksum(manifest: PluginManifest) -> str:
    """Return the deterministic checksum for the plugin database payload."""
    return _payload_checksum(_archive_inputs(manifest), manifest)


def validate_declared_database_schemas(manifest: PluginManifest) -> None:
    """Reject unsafe plugin schema and bridge API declarations."""
    validate_plugin_bridge_api_catalog()
    dependency_schemas: dict[str, str] = {}
    for schema in manifest.database_schemas:
        schema_name = schema.schema_name.strip().lower()
        if schema_name in PROTECTED_ORAC_SCHEMAS:
            raise PluginDatabaseValidationError(
                "Plugin database schema declaration targets protected Orac "
                f"schema '{schema.schema_name}'."
            )
        dependencies = schema.bridge_api_dependencies
        if len(set(dependencies)) != len(dependencies):
            raise PluginDatabaseValidationError(
                "Plugin bridge API dependency declarations must be unique for "
                f"schema '{schema.schema_name}'."
            )
        unknown_dependencies = sorted(
            set(dependencies) - set(PLUGIN_BRIDGE_API_CATALOG)
        )
        if unknown_dependencies:
            raise PluginDatabaseValidationError(
                "Plugin bridge API dependency declaration is not approved: "
                + ", ".join(unknown_dependencies)
            )
        for dependency_id in dependencies:
            previous_schema = dependency_schemas.get(dependency_id)
            if previous_schema is not None:
                raise PluginDatabaseValidationError(
                    "Plugin bridge API dependency declarations must be unique "
                    "across plugin schemas: "
                    f"{dependency_id} ({previous_schema}, {schema.schema_name})"
                )
            dependency_schemas[dependency_id] = schema.schema_name


def validate_schema_payload(
    schema_payload_path: Path,
    *,
    manifest: PluginManifest | None = None,
) -> None:
    """Reject plugin DDL payloads that reference protected Orac schemas.

    :param schema_payload_path: Plugin-local ``db/schema`` path.
    :param manifest: Optional manifest for owner/grant/Liquibase validation.
    :raises PluginDatabaseDeploymentError: when forbidden references are found.
    """
    violations = scan_protected_schema_references(schema_payload_path)
    if violations:
        details = "\n".join(violation.describe() for violation in violations)
        raise PluginDatabaseValidationError(
            "Plugin database payload references protected Orac schemas:\n" + details
        )
    if manifest is not None:
        validate_plugin_database_security(manifest)


def validate_plugin_database_security(manifest: PluginManifest) -> None:
    """Validate plugin database assets before any deployment tool can run."""
    schema_payload_path = plugin_schema_payload_path(manifest)
    declared_schemas = {
        schema.schema_name.strip().lower()
        for schema in manifest.database_schemas
        if schema.schema_name.strip()
    }
    if not declared_schemas:
        return

    sql_paths = [
        path
        for path in sorted(schema_payload_path.rglob("*"))
        if path.is_file() and path.suffix.lower() in _SCANNED_DDL_SUFFIXES
    ]
    if manifest.database_deployment.deployment_type == "liquibase":
        sql_paths.extend(validate_plugin_liquibase_changelog(manifest))

    declared_bridge_dependencies = {
        dependency_id
        for schema in manifest.database_schemas
        for dependency_id in schema.bridge_api_dependencies
    }
    referenced_bridge_dependencies: set[str] = set()
    violations: list[str] = []
    for path in sorted(set(sql_paths)):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in _PLUGIN_BRIDGE_REFERENCE.finditer(text):
            object_name = match.group(1).upper()
            dependency_id = next(
                (
                    candidate_id
                    for candidate_id, dependency in PLUGIN_BRIDGE_API_CATALOG.items()
                    if dependency["object_name"] == object_name
                ),
                None,
            )
            if dependency_id is None:
                violations.append(
                    f"{path}: ORAC_PLUGIN object '{object_name}' is not in the "
                    "host bridge API catalogue"
                )
            elif dependency_id not in declared_bridge_dependencies:
                violations.append(
                    f"{path}: ORAC_PLUGIN dependency '{dependency_id}' is not "
                    "declared by the plugin manifest"
                )
            else:
                referenced_bridge_dependencies.add(dependency_id)
        violations.extend(
            _validate_plugin_sql_file(
                path,
                declared_schemas=declared_schemas,
            )
        )
    unused_dependencies = sorted(
        declared_bridge_dependencies - referenced_bridge_dependencies
    )
    for dependency_id in unused_dependencies:
        violations.append(
            "Plugin manifest requests unused ORAC_PLUGIN dependency "
            f"'{dependency_id}'"
        )
    if violations:
        raise PluginDatabaseValidationError(
            "Plugin database payload failed security validation:\n"
            + "\n".join(violations)
        )


def validate_plugin_liquibase_changelog(manifest: PluginManifest) -> list[Path]:
    """Validate plugin Liquibase XML and return referenced SQL files."""
    controller_path = plugin_liquibase_controller_path(manifest)
    plugin_dir = manifest.plugin_dir.resolve()
    if not controller_path.is_file():
        raise PluginDatabaseValidationError(
            f"Plugin Liquibase controller is missing: {controller_path}"
        )
    if not controller_path.resolve().is_relative_to(plugin_dir):
        raise PluginDatabaseValidationError(
            f"Plugin Liquibase controller escapes plugin directory: {controller_path}"
        )

    referenced_sql: list[Path] = []
    visited: set[Path] = set()
    _collect_liquibase_sql_references(
        controller_path,
        plugin_dir=plugin_dir,
        referenced_sql=referenced_sql,
        visited=visited,
    )
    return referenced_sql


def _collect_liquibase_sql_references(
    changelog_path: Path,
    *,
    plugin_dir: Path,
    referenced_sql: list[Path],
    visited: set[Path],
) -> None:
    """Collect SQL files referenced by a Liquibase changelog tree."""
    resolved = changelog_path.resolve()
    if resolved in visited:
        return
    visited.add(resolved)
    if not resolved.is_relative_to(plugin_dir):
        raise PluginDatabaseValidationError(
            f"Plugin Liquibase changelog escapes plugin directory: {changelog_path}"
        )
    if any(part.lower() in _APEX_PATH_PARTS for part in resolved.parts):
        raise PluginDatabaseValidationError(
            f"APEX assets must not be included in plugin Liquibase changelog: {changelog_path}"
        )
    if resolved.suffix.lower() not in _SCANNED_CHANGELOG_SUFFIXES:
        _validate_plugin_referenced_sql_path(resolved)
        referenced_sql.append(resolved)
        return

    try:
        root = ElementTree.parse(resolved).getroot()
    except ElementTree.ParseError as exc:
        raise PluginDatabaseValidationError(
            f"Plugin Liquibase changelog XML is invalid: {changelog_path}: {exc}"
        ) from exc
    except OSError as exc:
        raise PluginDatabaseValidationError(
            f"Unable to read plugin Liquibase changelog {changelog_path}: {exc}"
        ) from exc

    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"include", "sqlFile"}:
            file_value = element.attrib.get("file") or element.attrib.get("path")
            if not file_value:
                raise PluginDatabaseValidationError(
                    f"Plugin Liquibase {tag} is missing file/path in {changelog_path}"
                )
            target = _resolve_liquibase_reference(
                file_value,
                source=resolved,
                relative_to_changelog=(
                    element.attrib.get("relativeToChangelogFile", "false").lower()
                    == "true"
                ),
                plugin_dir=plugin_dir,
            )
            if tag == "include":
                _collect_liquibase_sql_references(
                    target,
                    plugin_dir=plugin_dir,
                    referenced_sql=referenced_sql,
                    visited=visited,
                )
            else:
                _validate_plugin_referenced_sql_path(target)
                referenced_sql.append(target)
        elif tag == "includeAll":
            raise PluginDatabaseValidationError(
                f"Plugin Liquibase includeAll is not allowed: {changelog_path}"
            )


def _resolve_liquibase_reference(
    value: str,
    *,
    source: Path,
    relative_to_changelog: bool,
    plugin_dir: Path,
) -> Path:
    """Resolve and constrain a Liquibase file reference."""
    reference = Path(value)
    if reference.is_absolute():
        raise PluginDatabaseValidationError(
            f"Plugin Liquibase reference must be relative: {value}"
        )
    base = source.parent if relative_to_changelog else plugin_dir
    target = (base / reference).resolve()
    if not target.is_relative_to(plugin_dir):
        raise PluginDatabaseValidationError(
            f"Plugin Liquibase reference escapes plugin directory: {value}"
        )
    if not target.is_file():
        raise PluginDatabaseValidationError(
            f"Plugin Liquibase referenced file is missing: {value}"
        )
    return target


def _validate_plugin_referenced_sql_path(path: Path) -> None:
    """Reject referenced SQL paths that cross the APEX deployment boundary."""
    if path.suffix.lower() not in _SCANNED_DDL_SUFFIXES:
        raise PluginDatabaseValidationError(
            f"Plugin Liquibase sqlFile must reference SQL/PLSQL: {path}"
        )
    if any(part.lower() in _APEX_PATH_PARTS for part in path.parts):
        raise PluginDatabaseValidationError(
            f"APEX assets must not be included in plugin Liquibase deployment: {path}"
        )


def _validate_plugin_sql_file(
    path: Path,
    *,
    declared_schemas: set[str],
) -> list[str]:
    """Return security validation failures for one plugin SQL file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    violations: list[str] = []
    if _PUBLIC_SYNONYM.search(text):
        violations.append(f"{path}: public synonyms are not allowed")
    for match in _PRIVATE_SYNONYM_TARGET.finditer(text):
        target_owner = match.group(1).lower()
        if target_owner not in declared_schemas:
            violations.append(
                f"{path}: private synonym targets undeclared schema '{target_owner}'"
            )
    for match in _DDL_OWNER_STATEMENT.finditer(text):
        owner = match.group(1).lower()
        if owner not in declared_schemas:
            violations.append(f"{path}: DDL targets undeclared schema '{owner}'")
    for match in _GRANT_STATEMENT.finditer(text):
        owner = match.group(2).lower()
        grantee = match.group(4).lower()
        if owner not in declared_schemas:
            violations.append(f"{path}: grant source schema '{owner}' is not declared")
        if grantee not in declared_schemas and grantee not in _ALLOWED_PLUGIN_GRANTEES:
            violations.append(f"{path}: grant target schema '{grantee}' is not allowed")
    for match in _SCHEMA_QUALIFIED_REFERENCE.finditer(text):
        schema_name = match.group(1).lower()
        if (
            schema_name in PROTECTED_ORAC_SCHEMAS
            or schema_name in _ALLOWED_SHARED_PLUGIN_REFERENCE_SCHEMAS
        ):
            continue
        if schema_name.startswith("orac_") and schema_name not in declared_schemas:
            violations.append(
                f"{path}: references undeclared plugin-like schema '{schema_name}'"
            )
    return sorted(set(violations))


def scan_protected_schema_references(
    schema_payload_path: Path,
) -> list[ProtectedSchemaReference]:
    """Return all protected Orac schema references in a plugin schema payload."""
    if not schema_payload_path.exists():
        return []

    violations: list[ProtectedSchemaReference] = []
    for path in sorted(schema_payload_path.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _SCANNED_DDL_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            raise PluginDatabaseValidationError(
                f"Unable to read plugin DDL {path}: {exc}"
            ) from exc
        for line_number, line_text in enumerate(lines, start=1):
            for match in _PROTECTED_SCHEMA_REFERENCE.finditer(line_text):
                violations.append(
                    ProtectedSchemaReference(
                        path=path,
                        line_number=line_number,
                        schema_name=match.group(1).lower(),
                        line_text=line_text,
                    )
                )
    return violations


def _archive_inputs(manifest: PluginManifest) -> list[tuple[Path, str]]:
    """Return sorted source/archive-name pairs for deterministic packaging."""
    schema_payload_path = plugin_schema_payload_path(manifest)
    files: list[tuple[Path, str]] = [(manifest.manifest_path, "plugin.json")]
    for path in sorted(schema_payload_path.rglob("*")):
        if path.is_file():
            archive_name = Path("db") / "schema" / path.relative_to(schema_payload_path)
            files.append((path, archive_name.as_posix()))
    if manifest.database_deployment.deployment_type == "liquibase":
        liquibase_path = manifest.plugin_dir / "db" / "liquibase"
        if liquibase_path.is_dir():
            for path in sorted(liquibase_path.rglob("*")):
                if path.is_file():
                    archive_name = (
                        Path("db") / "liquibase" / path.relative_to(liquibase_path)
                    )
                    files.append((path, archive_name.as_posix()))
    return sorted(files, key=lambda item: item[1])


def _archive_manifest(
    *,
    manifest: PluginManifest,
    created_timestamp: str,
    payload_checksum: str,
) -> dict[str, Any]:
    """Build the generated archive manifest."""
    return {
        "plugin_id": manifest.plugin_id,
        "plugin_version": manifest.version,
        "schema_version": manifest.schema_version,
        "database": {
            "required": manifest.database_required,
            "on_missing": manifest.database_on_missing,
            "schemas": [
                {
                    "schema_name": schema.schema_name,
                    "purpose": schema.purpose,
                    "managed_by": schema.managed_by,
                    "minimum_version": schema.minimum_version,
                    "bridge_api_dependencies": list(schema.bridge_api_dependencies),
                    "version_check": {"enabled": schema.version_check.enabled},
                    "backup": (
                        None
                        if schema.backup is None
                        else {
                            "include": schema.backup.include,
                            "export_mode": schema.backup.export_mode,
                        }
                    ),
                }
                for schema in manifest.database_schemas
            ],
        },
        "payload_checksum": payload_checksum,
        "created_timestamp": created_timestamp,
        "source_plugin_directory": str(manifest.plugin_dir),
        "schema_payload_path": str(plugin_schema_payload_path(manifest)),
        "deployment_mode": "plugin_database_refresh",
        "deployment": {
            "type": manifest.database_deployment.deployment_type,
            "controller": manifest.database_deployment.controller,
        },
    }


def _payload_checksum(
    files: list[tuple[Path, str]],
    manifest: PluginManifest,
) -> str:
    """Return a deterministic checksum over canonical payload inputs."""
    digest = hashlib.sha256()
    digest.update(manifest.plugin_id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(manifest.version.encode("utf-8"))
    digest.update(b"\0")
    for path, archive_name in files:
        digest.update(archive_name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _already_deployed_sql(
    *,
    plugin_id: str,
    plugin_version: str,
    payload_checksum: str,
    schema_names: list[str],
    oracle_pdb: str,
    require_liquibase_tracking: bool = False,
) -> str:
    """Build the SQL*Plus state-check block for a plugin deployment payload."""
    lines = [
        "whenever sqlerror exit failure rollback",
        f"alter session set container={oracle_pdb};",
        "set heading off feedback off pagesize 0 verify off echo off",
        "set serveroutput on size unlimited",
        "declare",
        "  l_all_deployed varchar2(1 char) := 'Y';",
        "begin",
    ]
    for schema_name in schema_names:
        schema_literal = _sql_literal(schema_name.upper())
        lines.extend(
            [
                "  select case",
                "           when exists (",
                "                  select 1",
                "                    from dba_users",
                f"                   where username = {schema_literal}",
                "                )",
                "           then l_all_deployed",
                "           else 'N'",
                "         end",
                "    into l_all_deployed",
                "    from dual;",
                "  if orac_code.plugin_db_deployment_api.is_deployed(",
                f"       p_plugin_id           => {_sql_literal(plugin_id)},",
                f"       p_plugin_version      => {_sql_literal(plugin_version)},",
                f"       p_schema_name         => {_sql_literal(schema_name)},",
                f"       p_deployment_checksum => {_sql_literal(payload_checksum)}",
                "     ) <> 'Y'",
                "  then",
                "    l_all_deployed := 'N';",
                "  end if;",
            ]
        )
        if require_liquibase_tracking:
            lines.extend(
                [
                    "  select case",
                    "           when (",
                    "                  select count(1)",
                    "                    from dba_tables",
                    f"                   where owner = {schema_literal}",
                    "                     and table_name in (",
                    "                           'DATABASECHANGELOG',",
                    "                           'DATABASECHANGELOGLOCK'",
                    "                         )",
                    "                ) = 2",
                    "           then l_all_deployed",
                    "           else 'N'",
                    "         end",
                    "    into l_all_deployed",
                    "    from dual;",
                    "  if l_all_deployed = 'Y'",
                    "  then",
                    f"    execute immediate 'select case when count(1) > 0 then ''Y'' else ''N'' end from {schema_name.upper()}.databasechangelog'",
                    "       into l_all_deployed;",
                    "  end if;",
                ]
            )
    lines.extend(
        [
            "  dbms_output.put_line(",
            "    'ORAC_PLUGIN_DB_ALREADY_DEPLOYED=' || l_all_deployed",
            "  );",
            "end;",
            "/",
            "exit",
        ]
    )
    return "\n".join(lines)


def _mark_payload_deployed_sql(
    *,
    plugin_id: str,
    plugin_version: str,
    payload_checksum: str,
    schema_names: list[str],
    oracle_pdb: str,
    log_path: str,
) -> str:
    """Build the SQL*Plus block for recording verified existing payloads."""
    lines = [
        "whenever sqlerror exit failure rollback",
        f"alter session set container={oracle_pdb};",
        "set heading off feedback off pagesize 0 verify off echo off",
        "declare",
        "  l_row_version number;",
        "begin",
    ]
    for schema_name in schema_names:
        lines.extend(
            [
                "  orac_code.plugin_db_deployment_api.record_status(",
                f"    p_plugin_id           => {_sql_literal(plugin_id)},",
                f"    p_plugin_version      => {_sql_literal(plugin_version)},",
                f"    p_schema_name         => {_sql_literal(schema_name)},",
                f"    p_deployment_checksum => {_sql_literal(payload_checksum)},",
                "    p_deployment_status   => 'succeeded',",
                "    p_error_message       => null,",
                f"    p_log_path            => {_sql_literal(log_path)},",
                "    p_row_version         => l_row_version",
                "  );",
            ]
        )
    lines.extend(
        [
            "end;",
            "/",
            "exit",
        ]
    )
    return "\n".join(lines)


def expected_deployment_objects(
    *,
    manifest: PluginManifest,
    schema_payload_path: Path,
) -> dict[str, list[dict[str, str]]]:
    """Return expected live objects and grants for a deployed plugin payload."""
    validate_plugin_bridge_api_catalog()
    declared_schemas = {
        schema.schema_name.strip().lower()
        for schema in manifest.database_schemas
        if schema.schema_name.strip()
    }
    objects: set[tuple[str, str, str]] = set()
    grants: set[tuple[str, str, str, str]] = set()
    columns: set[tuple[str, str, str]] = set()

    for schema in manifest.database_schemas:
        for dependency_id in schema.bridge_api_dependencies:
            dependency = PLUGIN_BRIDGE_API_CATALOG[dependency_id]
            grants.add(
                (
                    dependency["owner"],
                    dependency["object_name"],
                    dependency["privilege"],
                    schema.schema_name.upper(),
                )
            )

    for path in sorted(schema_payload_path.rglob("*")):
        if not path.is_file():
            continue
        folder = path.parent.name.lower()
        if folder in _DEPLOYED_OBJECT_FOLDERS:
            qualified_name = _extract_qualified_object(path)
            if qualified_name is None:
                continue
            owner, object_name = qualified_name
            if owner.lower() not in declared_schemas:
                continue
            objects.add(
                (
                    owner.upper(),
                    object_name.upper(),
                    _DEPLOYED_OBJECT_FOLDERS[folder],
                )
            )
            columns.update(_extract_expected_columns(path, owner, object_name))
        elif folder == "grant":
            grants.update(_extract_grants(path, declared_schemas))

    return {
        "objects": [
            {"owner": owner, "object_name": object_name, "object_type": object_type}
            for owner, object_name, object_type in sorted(objects)
        ],
        "grants": [
            {
                "owner": owner,
                "object_name": object_name,
                "privilege": privilege,
                "grantee": grantee,
            }
            for owner, object_name, privilege, grantee in sorted(grants)
        ],
        "columns": [
            {"owner": owner, "object_name": object_name, "column_name": column_name}
            for owner, object_name, column_name in sorted(columns)
        ],
    }


def _payload_objects_deployed_sql(
    *,
    expected: dict[str, list[dict[str, str]]],
    oracle_pdb: str,
) -> str:
    """Build SQL*Plus verification block for deployed plugin objects."""
    lines = [
        "whenever sqlerror exit failure rollback",
        f"alter session set container={oracle_pdb};",
        "set heading off feedback off pagesize 0 verify off echo off",
        "set serveroutput on size unlimited",
        "declare",
        "  l_all_present varchar2(1 char) := 'Y';",
        "  l_count number;",
        "begin",
    ]
    for expected_object in expected["objects"]:
        lines.extend(
            [
                "  select count(*)",
                "    into l_count",
                "    from dba_objects",
                f"   where owner = {_sql_literal(expected_object['owner'])}",
                f"     and object_name = {_sql_literal(expected_object['object_name'])}",
                f"     and object_type = {_sql_literal(expected_object['object_type'])}",
                "     and status = 'VALID';",
                "  if l_count = 0",
                "  then",
                "    l_all_present := 'N';",
                "  end if;",
            ]
        )
    for column in expected.get("columns", []):
        lines.extend(
            [
                "  select count(*)",
                "    into l_count",
                "    from dba_tab_columns",
                f"   where owner = {_sql_literal(column['owner'])}",
                f"     and table_name = {_sql_literal(column['object_name'])}",
                f"     and column_name = {_sql_literal(column['column_name'])};",
                "  if l_count = 0",
                "  then",
                "    l_all_present := 'N';",
                "  end if;",
            ]
        )
    for grant in expected["grants"]:
        lines.extend(
            [
                "  select count(*)",
                "    into l_count",
                "    from dba_tab_privs",
                f"   where owner = {_sql_literal(grant['owner'])}",
                f"     and table_name = {_sql_literal(grant['object_name'])}",
                f"     and privilege = {_sql_literal(grant['privilege'])}",
                f"     and grantee = {_sql_literal(grant['grantee'])};",
                "  if l_count = 0",
                "  then",
                "    l_all_present := 'N';",
                "  end if;",
            ]
        )
    lines.extend(
        [
            "  dbms_output.put_line(",
            "    'ORAC_PLUGIN_DB_PAYLOAD_OBJECTS_DEPLOYED=' || l_all_present",
            "  );",
            "end;",
            "/",
            "exit",
        ]
    )
    return "\n".join(lines)


def _extract_qualified_object(path: Path) -> tuple[str, str] | None:
    """Extract the first schema-qualified object name from an object DDL file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"\b(?:create|create\s+or\s+replace|alter)\s+"
        r"(?:editionable\s+|noneditionable\s+)?"
        r"(?:table|view|materialized\s+view|package\s+body|package|"
        r"procedure|function|trigger|sequence|type\s+body|type)\s+"
        r"\"?([a-z][a-z0-9_]*)\"?\s*\.\s*\"?([a-z][a-z0-9_]*)\"?",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return None
    return match.group(1), match.group(2)


def _extract_expected_columns(
    path: Path,
    owner: str,
    object_name: str,
) -> set[tuple[str, str, str]]:
    """Extract explicitly declared deployment-verification columns from DDL."""
    text = path.read_text(encoding="utf-8", errors="replace")
    columns: set[tuple[str, str, str]] = set()
    for match in re.finditer(
        r"^\s*--\s*orac-expected-columns\s*:\s*(.+?)\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    ):
        for column_name in match.group(1).split(","):
            normalized_name = column_name.strip()
            if re.fullmatch(r"[a-z][a-z0-9_$#]*", normalized_name, re.IGNORECASE):
                columns.add(
                    (owner.upper(), object_name.upper(), normalized_name.upper())
                )
    return columns


def _extract_grants(
    path: Path,
    declared_schemas: set[str],
) -> set[tuple[str, str, str, str]]:
    """Extract simple object grants from a grant DDL file."""
    text = path.read_text(encoding="utf-8", errors="replace")
    grants: set[tuple[str, str, str, str]] = set()
    for match in re.finditer(
        r"\bgrant\s+([a-z_,\s]+?)\s+on\s+"
        r"\"?([a-z][a-z0-9_]*)\"?\s*\.\s*\"?([a-z][a-z0-9_]*)\"?"
        r"\s+to\s+\"?([a-z][a-z0-9_]*)\"?",
        text,
        re.IGNORECASE,
    ):
        owner = match.group(2)
        if owner.lower() not in declared_schemas:
            continue
        for privilege in re.split(r"\s*,\s*", match.group(1).strip()):
            normalized_privilege = re.sub(r"\s+", " ", privilege).upper()
            if normalized_privilege:
                grants.add(
                    (
                        owner.upper(),
                        match.group(3).upper(),
                        normalized_privilege,
                        match.group(4).upper(),
                    )
                )
    return grants


def _sql_literal(value: str) -> str:
    """Return a SQL literal with embedded quotes escaped."""
    return "'" + value.replace("'", "''") + "'"


def _validate_oracle_identifier(value: str, label: str) -> None:
    """Raise when a generated SQL identifier is not conservative and safe."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid {label}: {value}")


def _schema_identifier(schema_name: str) -> str:
    """Return a validated uppercase Oracle schema identifier."""
    identifier = schema_name.strip().upper()
    _validate_oracle_identifier(identifier, "schema_name")
    return identifier


def _quoted_oracle_password(password: str) -> str:
    """Return a quoted Oracle password literal for generated create-user DDL."""
    return '"' + password.replace('"', '""') + '"'


def _sha256_file(path: Path) -> str:
    """Return a SHA-256 checksum for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        shutil.copyfileobj(handle, _HashWriter(digest))
    return digest.hexdigest()


def _add_file_to_tar(
    tar: tarfile.TarFile, source_path: Path, archive_name: str
) -> None:
    """Add a file to a tar archive with deterministic metadata."""
    data = source_path.read_bytes()
    _add_bytes_to_tar(tar, archive_name, data)


def _add_bytes_to_tar(tar: tarfile.TarFile, archive_name: str, data: bytes) -> None:
    """Add bytes to a tar archive with deterministic metadata."""
    info = tarfile.TarInfo(archive_name)
    info.size = len(data)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))


class _HashWriter:
    """Small binary writer adapter that updates a hashlib object."""

    def __init__(self, digest: "hashlib._Hash") -> None:
        self._digest = digest

    def write(self, data: bytes) -> int:
        """Update the wrapped digest and return bytes consumed."""
        self._digest.update(data)
        return len(data)
