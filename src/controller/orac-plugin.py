#!/usr/bin/env python3
"""Package, install, inspect, and validate Orac plugins."""

# Author: Clive Bostock
# Date: 07-Jun-2026
# Description: Command-line interface for Orac-owned plugin installation.
#
# Purpose: Package and install registered Orac plugins.
# Usage: bin/orac-plugin.sh install --bundled home_assistant

from __future__ import annotations

import argparse
from contextlib import nullcontext
from dataclasses import asdict
import getpass
import hashlib
import json
from pathlib import Path
import signal
import sys
import threading
import time
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_installer import PluginInstallationError
from model.plugin_installer import PluginRemovalConfirmationError
from model.plugin_installer import PluginInstaller
from model.plugin_execution_lock import PluginExecutionLock
from model.plugin_execution_lock import PluginMaintenanceError
from model.plugin_package import PluginPackageError
from model.plugin_registry import PluginRegistryError
from model.plugin_registry import PluginRegistryStore
from model.plugin_runtime import PluginRuntimeError
from model.plugin_service_lifecycle import PluginServiceLifecycleStore
from model.plugin_service_manager import PluginServiceManager
from model.plugin_database_deployment import PluginDatabaseDeploymentError
from model.plugin_apex_installation import PluginApexAppInstallError

VALID_SERVICE_POLICIES = ("auto", "manual", "disabled")


def build_parser() -> argparse.ArgumentParser:
    """Build the plugin management argument parser."""
    parser = argparse.ArgumentParser(description="Package and install Orac plugins.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install one or more plugins.")
    source = install.add_mutually_exclusive_group(required=True)
    source.add_argument("archive", nargs="?", type=Path, help="Plugin .tar.gz package.")
    source.add_argument("--source", type=Path, help="Development plugin directory.")
    source.add_argument("--bundled", metavar="PLUGIN_ID", help="Bundled plugin id.")
    source.add_argument(
        "--all", action="store_true", help="Install all bundled plugins."
    )
    install.add_argument(
        "--keep-failed-staging",
        action="store_true",
        help="Retain failed staging files for diagnosis.",
    )

    package = subparsers.add_parser("package", help="Build a plugin tarball.")
    package.add_argument("--source", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)

    list_plugins = subparsers.add_parser(
        "list",
        help="List currently installed plugins.",
    )
    list_plugins.add_argument(
        "--json",
        action="store_true",
        help="Emit plugin inventory as JSON.",
    )
    list_plugins.add_argument(
        "--source-packages",
        action="store_true",
        help="Also show unpacked source packages separately from installed state.",
    )

    status = subparsers.add_parser("status", help="Show registered plugin status.")
    status.add_argument("plugin_id")
    check = subparsers.add_parser("check", help="Validate registered plugin readiness.")
    check.add_argument("plugin_id")

    for command in ("enable", "disable"):
        lifecycle = subparsers.add_parser(
            command, help=f"{command.title()} an installed plugin."
        )
        lifecycle.add_argument("plugin_id")
    history = subparsers.add_parser(
        "history", help="Show historical removal operations."
    )
    history.add_argument("plugin_id")
    history.add_argument("--json", action="store_true")
    remove = subparsers.add_parser(
        "remove", help="Remove a plugin and its verified dedicated schemas."
    )
    remove.add_argument("plugin_id")
    remove.add_argument(
        "--keep-schema",
        action="store_true",
        help="Retain dedicated schemas locked and detached from Orac.",
    )
    remove.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect resources without changing them.",
    )
    remove.add_argument(
        "--json", action="store_true", help="Emit the removal result as JSON."
    )
    remove.add_argument(
        "--yes", action="store_true", help="Confirm removal non-interactively."
    )
    remove.add_argument(
        "--confirm-schema-drop",
        metavar="PLUGIN_ID",
        help="Explicitly acknowledge destroying this plugin's dedicated schemas.",
    )

    service = subparsers.add_parser(
        "service",
        help="Run narrow foreground service operations for an installed plugin.",
    )
    service_subparsers = service.add_subparsers(
        dest="service_command",
        required=True,
    )
    service_run = service_subparsers.add_parser(
        "run",
        help="Run one installed service plugin in the foreground.",
    )
    service_run.add_argument("plugin_id")
    service_run.add_argument(
        "service_code",
        nargs="?",
        default=None,
        help="Service code to run when the plugin exposes multiple services.",
    )
    service_run.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
        help="Stop the foreground service after this many seconds.",
    )
    service_status = service_subparsers.add_parser(
        "status",
        help="Show plugin service lifecycle status.",
    )
    service_status.add_argument("plugin_id", nargs="?")
    service_status.add_argument("service_code", nargs="?")
    service_status.add_argument(
        "--require-running",
        action="store_true",
        help="Fail unless every matching service is running with an active lease.",
    )
    service_policy = service_subparsers.add_parser(
        "policy",
        help="Set plugin service startup policy.",
    )
    service_policy.add_argument("plugin_id")
    service_policy.add_argument("service_code")
    service_policy.add_argument("policy", choices=VALID_SERVICE_POLICIES)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Orac plugin management CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "remove":
        if args.keep_schema and args.confirm_schema_drop is not None:
            parser.error(
                "--keep-schema and --confirm-schema-drop are mutually exclusive"
            )
        if (
            args.confirm_schema_drop is not None
            and args.confirm_schema_drop != args.plugin_id
        ):
            parser.error("--confirm-schema-drop must match the plugin ID being removed")
    execution_lock = (
        nullcontext()
        if args.command in {"remove", "enable", "disable"}
        else PluginExecutionLock(
            PROJECT_ROOT,
            exclusive=(
                args.command in {"install", "check", "enable", "disable", "remove"}
                or (args.command == "service" and args.service_command == "policy")
            ),
        )
    )
    try:
        execution_lock.__enter__()
        if args.command == "service":
            if args.service_command == "run":
                return run_plugin_service(
                    args.plugin_id,
                    service_code=args.service_code,
                    duration_seconds=args.duration_seconds,
                )
            if args.service_command == "status":
                return show_plugin_service_status(
                    plugin_id=args.plugin_id,
                    service_code=args.service_code,
                    require_running=args.require_running,
                )
            if args.service_command == "policy":
                return set_plugin_service_policy(
                    plugin_id=args.plugin_id,
                    service_code=args.service_code,
                    policy=args.policy,
                )
            return 1
        installer = PluginInstaller(
            keep_failed_staging=getattr(args, "keep_failed_staging", False)
        )
        if args.command == "package":
            archive = installer.package(args.source, args.output)
            print(archive)
            print(f"sha256: {_sha256_file(archive)}")
            return 0
        if args.command == "list":
            entries = installer.list_plugins(include_source=args.source_packages)
            if args.json:
                print(json.dumps(entries, indent=2, default=str, sort_keys=True))
            else:
                print(_format_plugin_inventory(entries))
            return 0
        if args.command in {"enable", "disable"}:
            getattr(installer, args.command)(args.plugin_id)
            print(f"Plugin '{args.plugin_id}' {args.command}d.")
            return 0
        if args.command == "history":
            records = installer.history(args.plugin_id)
            if args.json:
                print(json.dumps(records, indent=2, default=str, sort_keys=True))
            elif not records:
                print(f"No removal history for '{args.plugin_id}'.")
            else:
                for record in records:
                    state = "completed" if record.get("completed_on") else "incomplete"
                    print(
                        f"{record['removal_id']} {record['plugin_version']} {record['schema_disposition']}: {state}"
                    )
            return 0
        if args.command == "remove":
            result = installer.remove(
                args.plugin_id,
                keep_schema=args.keep_schema,
                dry_run=args.dry_run,
                confirmed_by=getpass.getuser(),
                confirm=lambda inventory: _confirm_plugin_removal(args, inventory),
            )
            if args.json:
                print(json.dumps(asdict(result), indent=2, default=str, sort_keys=True))
            else:
                print(f"{result.plugin_id}: {result.status} - {result.message}")
                if args.dry_run:
                    _print_removal_inventory(result.inventory)
            return 0
        if args.command == "install":
            if args.all:
                results = installer.install_all_bundled()
            elif args.bundled:
                results = [installer.install_bundled(args.bundled)]
            elif args.source:
                results = [installer.install_source(args.source)]
            else:
                results = [installer.install_archive(args.archive)]
            for result in results:
                print(
                    f"{result.plugin_id} {result.version}: {result.status} - "
                    f"{result.message}"
                )
                for warning in result.warnings:
                    print(f"Warning: {warning}", file=sys.stderr)
            return 0 if all(result.enabled for result in results) else 1
        if args.command == "status":
            status = installer.status(args.plugin_id)
            if status is None:
                print(f"Plugin '{args.plugin_id}' is not registered.", file=sys.stderr)
                return 1
            print(json.dumps(status, indent=2, default=str, sort_keys=True))
            return 0
        if args.command == "check":
            result = installer.check(args.plugin_id)
            print(f"{result.plugin_id} {result.version}: {result.message}")
            for warning in result.warnings:
                print(f"Warning: {warning}", file=sys.stderr)
            return 0
    except PluginRemovalConfirmationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except (
        PluginInstallationError,
        PluginPackageError,
        PluginRegistryError,
        PluginRuntimeError,
        PluginMaintenanceError,
        PluginDatabaseDeploymentError,
        PluginApexAppInstallError,
        OSError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        execution_lock.__exit__(None, None, None)
    return 1


def _print_removal_inventory(inventory: dict[str, Any], *, stream: Any = None) -> None:
    """Display credential-free resource scope before asking for confirmation."""
    stream = stream or sys.stdout
    if not inventory:
        return
    print(
        f"Plugin: {inventory['plugin_id']} {inventory['plugin_version']}", file=stream
    )
    print(f"Database/PDB: {inventory['database']['database_identity']}", file=stream)
    names = [item["schema_name"] for item in inventory["database"]["schemas"]]
    print("Dedicated schemas: " + (", ".join(names) or "none"), file=stream)
    if not names and inventory["schema_disposition"] == "KEEP":
        print("This plugin has no dedicated schema; --keep-schema has no effect.", file=stream)
    print(f"Schema disposition: {inventory['schema_disposition']}", file=stream)
    print(
        "APEX apps: "
        + (", ".join(item["app_alias"] for item in inventory["apex"]) or "none"),
        file=stream,
    )
    for directory in inventory["directories"]:
        print(f"Remove {directory['kind']}: {directory['path']}", file=stream)
    print("Plugin secrets and routing-cache entries will be removed.", file=stream)
    print(
        "Use --keep-schema to retain dedicated schemas locked and detached.",
        file=stream,
    )


def _confirm_plugin_removal(
    args: argparse.Namespace, inventory: dict[str, Any]
) -> bool:
    """Require explicit acknowledgement of the displayed plugin and schema loss."""
    destroys_schemas = not args.keep_schema and any(
        item.get("present") == 1 for item in inventory["database"]["schemas"]
    )
    if args.yes:
        if destroys_schemas and args.confirm_schema_drop != args.plugin_id:
            raise PluginRemovalConfirmationError(
                "Schema destruction also requires --confirm-schema-drop "
                + args.plugin_id
            )
        return True
    if not sys.stdin.isatty():
        raise PluginRemovalConfirmationError("Non-interactive removal requires --yes.")
    _print_removal_inventory(inventory, stream=sys.stderr if args.json else sys.stdout)
    phrase = "REMOVE " + args.plugin_id
    if destroys_schemas:
        phrase += " AND DROP SCHEMAS"
    elif args.keep_schema:
        phrase += " KEEP SCHEMAS"
    try:
        return input(f"Type '{phrase}' to confirm: ").strip() == phrase
    except (EOFError, KeyboardInterrupt):
        return False


class _ConsoleLogger:
    """Small logger adapter used by foreground operator commands."""

    def log_debug(self, message: str) -> None:
        """Write debug messages to standard output."""
        print(message)

    def log_info(self, message: str) -> None:
        """Write informational messages to standard output."""
        print(message)

    def log_warning(self, message: str) -> None:
        """Write warnings to standard error."""
        print(f"Warning: {message}", file=sys.stderr)

    def log_error(self, message: str) -> None:
        """Write errors to standard error."""
        print(f"Error: {message}", file=sys.stderr)


def run_plugin_service(
    plugin_id: str,
    *,
    service_code: str | None = None,
    duration_seconds: float | None = None,
    registry_store: Any | None = None,
    service_manager: PluginServiceManager | None = None,
    logger: Any | None = None,
    sleep: Any = time.sleep,
) -> int:
    """Run one installed service plugin in the foreground.

    Args:
        plugin_id: Installed plugin id to run.
        duration_seconds: Optional maximum runtime before stopping the service.
        registry_store: Optional registry store override for tests.
        service_manager: Optional service manager override for tests.
        logger: Optional logger override.
        sleep: Sleep function override for tests.

    Returns:
        Process-style status code.
    """
    if duration_seconds is not None and duration_seconds <= 0:
        raise ValueError("--duration-seconds must be greater than zero.")

    logger = logger or _ConsoleLogger()
    registry_store = registry_store or PluginRegistryStore(logger=logger)
    if hasattr(registry_store, "enabled_manifest"):
        manifest = registry_store.enabled_manifest(plugin_id)
        manifests = [manifest] if manifest is not None else []
    else:
        manifests = [
            manifest
            for manifest in registry_store.enabled_manifests()
            if manifest.plugin_id == plugin_id
        ]
    if not manifests:
        raise PluginRuntimeError(
            f"Plugin '{plugin_id}' is not registered, enabled, and ready to run."
        )
    manifest = manifests[0]
    if manifest.runtime_mode not in {"service", "hybrid"}:
        raise PluginRuntimeError(f"Plugin '{plugin_id}' is not a service plugin.")

    service_manager = service_manager or PluginServiceManager(logger=logger)
    service_manager.register_manifests([manifest])
    resolved_service_code = _resolve_service_code(
        plugin_id,
        service_code,
        service_manager.service_ids(),
    )

    service_id = (
        plugin_id
        if resolved_service_code == "default"
        else f"{plugin_id}:{resolved_service_code}"
    )
    print(f"Starting foreground diagnostic plugin service '{service_id}'.")
    if not service_manager.start(plugin_id, resolved_service_code):
        print(
            json.dumps(service_manager.status(), indent=2, default=str, sort_keys=True)
        )
        return 1

    stop_requested = threading.Event()
    previous_handlers: dict[int, Any] = {}

    def _request_stop(_signum: int, _frame: Any) -> None:
        stop_requested.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, _request_stop)
        except ValueError:
            pass

    started = time.monotonic()
    failed = False
    try:
        while not stop_requested.is_set():
            status = service_manager.status()["services"].get(service_id, {})
            state = status.get("state")
            if state == "failed":
                failed = True
                break
            if (
                duration_seconds is not None
                and time.monotonic() - started >= duration_seconds
            ):
                break
            sleep(0.25)
    finally:
        for signum, handler in previous_handlers.items():
            try:
                signal.signal(signum, handler)
            except ValueError:
                pass
        service_manager.stop(plugin_id, resolved_service_code)

    status = service_manager.status()
    print(json.dumps(status, indent=2, default=str, sort_keys=True))
    final_state = status.get("services", {}).get(service_id, {}).get("state")
    return 0 if not failed and final_state == "stopped" else 1


def show_plugin_service_status(
    *,
    plugin_id: str | None = None,
    service_code: str | None = None,
    require_running: bool = False,
    lifecycle_store: PluginServiceLifecycleStore | None = None,
) -> int:
    """Print service status and optionally assert running, actively leased rows."""
    lifecycle_store = lifecycle_store or PluginServiceLifecycleStore()
    if plugin_id and service_code and not require_running:
        rows = [lifecycle_store.get_service(plugin_id, service_code)]
    else:
        rows = [
            row
            for row in lifecycle_store.list_services()
            if (plugin_id is None or row.plugin_id == plugin_id)
            and (service_code is None or row.service_code == service_code)
        ]
    print(
        json.dumps(
            [row.__dict__ for row in rows], indent=2, default=str, sort_keys=True
        )
    )
    if not require_running:
        return 0
    return (
        0
        if rows
        and all(
            row.current_state == "running" and row.lease_active_yn == "Y"
            for row in rows
        )
        else 1
    )


def set_plugin_service_policy(
    *,
    plugin_id: str,
    service_code: str,
    policy: str,
    lifecycle_store: PluginServiceLifecycleStore | None = None,
) -> int:
    """Set plugin service startup policy and print the updated lifecycle row."""
    if policy not in VALID_SERVICE_POLICIES:
        values = ", ".join(VALID_SERVICE_POLICIES)
        raise ValueError(f"policy must be one of: {values}")

    lifecycle_store = lifecycle_store or PluginServiceLifecycleStore()
    updated = lifecycle_store.set_service_policy(
        plugin_id=plugin_id,
        service_code=service_code,
        policy=policy,
    )
    print(json.dumps(updated.__dict__, indent=2, default=str, sort_keys=True))
    return 0


def _format_plugin_inventory(entries: list[dict[str, Any]]) -> str:
    """Format plugin inventory entries as a deterministic operator table."""
    if not entries:
        return "No plugins found."

    columns = (
        ("plugin_id", "PLUGIN"),
        ("name", "NAME"),
        ("installed", "INSTALLED"),
        ("installed_artifact_status", "ARTIFACT"),
        ("unpacked", "UNPACKED"),
        ("installed_version", "INSTALLED_VERSION"),
        ("unpacked_version", "UNPACKED_VERSION"),
        ("enabled", "ENABLED"),
        ("install_status", "INSTALL_STATUS"),
        ("readiness_status", "READINESS_STATUS"),
    )
    rows = [
        [_inventory_cell(entry.get(key)) for key, _heading in columns]
        for entry in entries
    ]
    widths = [
        max(len(heading), *(len(row[index]) for row in rows))
        for index, (_key, heading) in enumerate(columns)
    ]
    lines = [
        "  ".join(
            heading.ljust(widths[index])
            for index, (_key, heading) in enumerate(columns)
        )
    ]
    lines.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    )

    errors = [str(entry["error"]) for entry in entries if entry.get("error")]
    errors.extend(
        f"{entry.get('plugin_id')}: {entry['installed_artifact_error']}"
        for entry in entries
        if entry.get("installed_artifact_error")
    )
    if errors:
        lines.append("")
        lines.extend(f"Inventory error: {error}" for error in errors)
    return "\n".join(lines)


def _inventory_cell(value: Any) -> str:
    """Return a compact printable value for one plugin inventory cell."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None or value == "":
        return "-"
    return str(value)


def _resolve_service_code(
    plugin_id: str,
    service_code: str | None,
    service_ids: tuple[str, ...],
) -> str:
    """Resolve optional CLI service code, preserving single-service compatibility."""
    if service_code:
        return service_code
    matching = [
        service_id
        for service_id in service_ids
        if service_id == plugin_id or service_id.startswith(f"{plugin_id}:")
    ]
    if len(matching) == 1:
        service_id = matching[0]
        return "default" if service_id == plugin_id else service_id.split(":", 1)[1]
    raise PluginRuntimeError(
        f"Plugin '{plugin_id}' has multiple services; specify service_code."
    )


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a generated package."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
