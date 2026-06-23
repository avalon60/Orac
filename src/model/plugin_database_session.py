"""Managed runtime database sessions for Orac plugins."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Provides the ORAC_PLUGIN database session facade exposed to plugin runtimes.

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable, Protocol

from model.plugin_database_deployment import PROTECTED_ORAC_SCHEMAS

__author__ = "Clive Bostock"
__date__ = "04-Jun-2026"
__description__ = "Provides controlled ORAC_PLUGIN database access to plugins."


ORAC_PLUGIN_DATABASE_USER = "ORAC_PLUGIN"
DEFAULT_PLUGIN_DATABASE_CONNECTION_NAME = "orac-plugin"
FORBIDDEN_PLUGIN_CREDENTIAL_USERS = frozenset(
    {
        "ORAC",
        "ORAC_CORE",
        "ORAC_API",
        "ORAC_CODE",
        "ORAC_APX_PUB",
        "ORAC_HA",
        "SYSTEM",
        "SYS",
    }
)

_PLSQL_IDENTIFIER = re.compile(
    r"^[a-z][a-z0-9_$#]*(\.[a-z][a-z0-9_$#]*){0,2}$",
    re.IGNORECASE,
)
_MUTATING_SQL = re.compile(
    r"\b(insert|update|delete|merge|create|alter|drop|truncate|grant|revoke)\b",
    re.IGNORECASE,
)


class PluginDatabaseSessionError(RuntimeError):
    """Raised when a managed plugin database session cannot be created or used."""


class _RuntimeDBSession(Protocol):
    """Minimal DBSession protocol required by the managed plugin facade."""

    user: str

    def cursor(self) -> Any:
        """Return a context-managed Oracle cursor."""

    def commit(self) -> None:
        """Commit the current transaction."""

    def rollback(self) -> None:
        """Roll back the current transaction."""

    def close(self) -> None:
        """Close the database session."""


class OracPluginDatabaseSession:
    """Narrow runtime database facade exposed to plugin code.

    The facade deliberately avoids exposing the raw ``DBSession`` object. Plugins
    can call granted package APIs, run tightly scoped anonymous PL/SQL, fetch
    rows for approved read paths, and manage transactions explicitly.
    """

    def __init__(
        self,
        *,
        db_session: _RuntimeDBSession,
        connected_username: str,
    ) -> None:
        """Initialise the managed session wrapper.

        Args:
            db_session: Existing Orac-owned database connection.
            connected_username: Username used by the underlying connection.

        Raises:
            PluginDatabaseSessionError: If the connection is not ORAC_PLUGIN.
        """
        username = _normalise_username(connected_username)
        if username != ORAC_PLUGIN_DATABASE_USER:
            raise PluginDatabaseSessionError(
                "Plugin runtime database sessions must connect as ORAC_PLUGIN."
            )
        self._db_session = db_session
        self.connected_username = username

    def __enter__(self) -> "OracPluginDatabaseSession":
        """Return this session for context-manager usage."""
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        """Roll back failed work and close the underlying session."""
        try:
            if exc_type is not None:
                self.rollback()
        finally:
            self.close()

    def call_procedure(
        self,
        procedure_name: str,
        parameters: list[Any] | tuple[Any, ...] | None = None,
        *,
        auto_commit: bool = False,
    ) -> list[Any]:
        """Call a granted PL/SQL procedure through ORAC_PLUGIN.

        Args:
            procedure_name: Procedure name, usually ``schema.package.procedure``.
            parameters: Positional bind values for the procedure call.
            auto_commit: Whether to commit after the call.

        Returns:
            The list returned by ``cursor.callproc``.
        """
        safe_name = self._validate_plsql_identifier(procedure_name)
        with self._db_session.cursor() as cursor:
            result = cursor.callproc(safe_name, list(parameters or []))
        if auto_commit:
            self.commit()
        return list(result or [])

    def call_function(
        self,
        function_name: str,
        *,
        return_type: Any,
        parameters: list[Any] | tuple[Any, ...] | None = None,
        auto_commit: bool = False,
    ) -> Any:
        """Call a granted PL/SQL function through ORAC_PLUGIN."""
        safe_name = self._validate_plsql_identifier(function_name)
        with self._db_session.cursor() as cursor:
            result = cursor.callfunc(safe_name, return_type, list(parameters or []))
        if auto_commit:
            self.commit()
        return result

    def call_plsql(
        self,
        plsql_block: str,
        bind_vars: dict[str, Any] | None = None,
        *,
        auto_commit: bool = False,
    ) -> None:
        """Execute a restricted anonymous PL/SQL block.

        This method intentionally does not reuse ``DBSession.run_plsql_block``
        because that helper commits automatically and assumes a ``b_status`` bind
        convention. Direct DML and DDL text is rejected here; plugins should call
        granted package APIs for writes.
        """
        block = str(plsql_block or "").strip()
        if not block:
            raise PluginDatabaseSessionError("PL/SQL block is required.")
        if not (
            block.lower().startswith("begin")
            or block.lower().startswith("declare")
        ):
            raise PluginDatabaseSessionError(
                "Plugin PL/SQL execution must use an anonymous PL/SQL block."
            )
        if _MUTATING_SQL.search(block):
            raise PluginDatabaseSessionError(
                "Plugin PL/SQL blocks must not contain direct DML, DDL, or grants."
            )
        with self._db_session.cursor() as cursor:
            cursor.execute(block, dict(bind_vars or {}))
        if auto_commit:
            self.commit()

    def fetch_dicts(
        self,
        sql_query: str,
        bind_vars: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch rows from an approved read query as dictionaries."""
        sql = str(sql_query or "").strip()
        if not sql:
            raise PluginDatabaseSessionError("SQL query is required.")
        if not (
            sql.lower().startswith("select")
            or sql.lower().startswith("with")
        ):
            raise PluginDatabaseSessionError(
                "Plugin read access is limited to SELECT queries."
            )
        if _MUTATING_SQL.search(sql):
            raise PluginDatabaseSessionError(
                "Plugin read access must not contain mutating SQL keywords."
            )
        with self._db_session.cursor() as cursor:
            cursor.execute(sql, dict(bind_vars or {}))
            rows = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in rows]

    def commit(self) -> None:
        """Commit outstanding plugin database work."""
        self._db_session.commit()

    def rollback(self) -> None:
        """Roll back outstanding plugin database work."""
        self._db_session.rollback()

    def close(self) -> None:
        """Close the underlying ORAC_PLUGIN connection."""
        self._db_session.close()

    @staticmethod
    def _validate_plsql_identifier(identifier: str) -> str:
        """Validate a PL/SQL package/procedure/function identifier."""
        value = str(identifier or "").strip()
        if not _PLSQL_IDENTIFIER.match(value):
            raise PluginDatabaseSessionError(
                f"Invalid plugin PL/SQL identifier: {identifier!r}"
            )
        schema_name = value.split(".", 1)[0].lower()
        if schema_name in PROTECTED_ORAC_SCHEMAS:
            raise PluginDatabaseSessionError(
                f"Plugin runtime cannot call protected schema '{schema_name}'."
            )
        return value


class OracPluginDatabaseSessionFactory:
    """Creates managed ORAC_PLUGIN sessions from Orac's credential store."""

    def __init__(
        self,
        *,
        config_mgr: Any | None = None,
        connection_name: str | None = None,
        project_identifier: str | None = None,
        user_security_factory: Callable[..., Any] | None = None,
        db_session_factory: Callable[..., _RuntimeDBSession] | None = None,
        config_dir: Path | None = None,
        logger: Any | None = None,
    ) -> None:
        """Initialise the factory.

        Args:
            config_mgr: Optional Orac configuration manager.
            connection_name: Saved DSN connection name. Defaults to
                ``database.plugin_connection_name`` or ``orac-plugin``.
            project_identifier: Credential-store project identifier override.
            user_security_factory: Injectable ``UserSecurity`` factory for tests.
            db_session_factory: Injectable DB session factory for tests.
            config_dir: Optional Oracle network configuration directory.
            logger: Optional Orac logger.
        """
        self._config_mgr = config_mgr
        self._connection_name = connection_name
        self._project_identifier = project_identifier
        self._user_security_factory = user_security_factory
        self._db_session_factory = db_session_factory
        self._config_dir = config_dir
        self._logger = logger

    def create(self) -> OracPluginDatabaseSession:
        """Create one managed ORAC_PLUGIN database session."""
        connection_name = self._resolved_connection_name()
        project_identifier = self._resolved_project_identifier()
        user_security = self._create_user_security(project_identifier)
        try:
            username, password, dsn = user_security.named_connection_creds(
                connection_name=connection_name
            )
            wallet_zip_path = user_security.connection_property(
                connection_name=connection_name,
                property_key="wallet_zip_path",
                default_value="",
            )
        except Exception as exc:
            raise PluginDatabaseSessionError(
                "ORAC_PLUGIN database credentials are unavailable. Configure "
                f"saved DSN connection '{connection_name}'."
            ) from exc

        username_normalised = _normalise_username(username)
        if username_normalised in FORBIDDEN_PLUGIN_CREDENTIAL_USERS:
            raise PluginDatabaseSessionError(
                "Plugin runtime database sessions cannot use protected "
                f"database user '{username_normalised}'."
            )
        if username_normalised != ORAC_PLUGIN_DATABASE_USER:
            raise PluginDatabaseSessionError(
                "Plugin runtime database sessions must use saved credentials "
                "for ORAC_PLUGIN."
            )

        db_session = self._create_db_session(
            wallet_zip_path=wallet_zip_path or "",
            username=username,
            password=password,
            dsn=dsn,
        )
        self._log_debug(
            f"Created managed plugin database session using saved connection "
            f"'{connection_name}' as ORAC_PLUGIN."
        )
        return OracPluginDatabaseSession(
            db_session=db_session,
            connected_username=username,
        )

    def _resolved_connection_name(self) -> str:
        """Return the saved DSN connection name for plugin runtime sessions."""
        if self._connection_name:
            return self._connection_name
        if self._config_mgr is not None:
            value = self._config_mgr.config_value(
                section="database",
                key="plugin_connection_name",
                default=DEFAULT_PLUGIN_DATABASE_CONNECTION_NAME,
            )
            return str(value or DEFAULT_PLUGIN_DATABASE_CONNECTION_NAME).strip()
        return DEFAULT_PLUGIN_DATABASE_CONNECTION_NAME

    def _resolved_project_identifier(self) -> str:
        """Return the credential-store project identifier."""
        if self._project_identifier:
            return self._project_identifier
        if self._config_mgr is not None:
            value = self._config_mgr.config_value(
                section="global",
                key="project_identifier",
                default="Orac",
            )
            return str(value or "Orac").strip()
        return "Orac"

    def _create_user_security(self, project_identifier: str) -> Any:
        """Create the existing Orac credential-store adapter."""
        if self._user_security_factory is not None:
            return self._user_security_factory(
                project_identifier=project_identifier,
                resource_type="dsn",
            )
        from lib.user_security import UserSecurity

        return UserSecurity(
            project_identifier=project_identifier,
            resource_type="dsn",
        )

    def _create_db_session(
        self,
        *,
        wallet_zip_path: str,
        username: str,
        password: str,
        dsn: str,
    ) -> _RuntimeDBSession:
        """Create the underlying DBSession without exposing it to plugins."""
        if self._db_session_factory is not None:
            return self._db_session_factory(
                wallet_zip_path=wallet_zip_path,
                verbose=False,
                user=username,
                password=password,
                dsn=dsn,
                config_dir=self._config_dir,
            )
        from lib.session_manager import DBSession

        kwargs: dict[str, Any] = {
            "wallet_zip_path": wallet_zip_path,
            "verbose": False,
            "user": username,
            "password": password,
            "dsn": dsn,
        }
        if self._config_dir is not None:
            kwargs["config_dir"] = self._config_dir
        return DBSession(**kwargs)

    def _log_debug(self, message: str) -> None:
        """Write a debug message when a logger is available."""
        if self._logger is not None and hasattr(self._logger, "log_debug"):
            self._logger.log_debug(message)


def _normalise_username(username: str) -> str:
    """Normalise an Oracle username for credential safety checks."""
    return str(username or "").strip().strip('"').upper()
