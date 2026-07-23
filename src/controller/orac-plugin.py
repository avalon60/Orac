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
from model.plugin_installer import PluginInstaller
from model.plugin_package import PluginPackageError
from model.plugin_registry import PluginRegistryError
from model.plugin_registry import PluginRegistryStore
from model.plugin_runtime import PluginRuntimeError
from model.plugin_service_lifecycle import PluginServiceLifecycleStore
from model.plugin_service_manager import PluginServiceManager

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
        help="List installed and unpacked plugins.",
    )
    list_plugins.add_argument(
        "--json",
        action="store_true",
        help="Emit plugin inventory as JSON.",
    )

    status = subparsers.add_parser("status", help="Show registered plugin status.")
    status.add_argument("plugin_id")
    check = subparsers.add_parser("check", help="Validate registered plugin readiness.")
    check.add_argument("plugin_id")

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
    try:
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
            entries = installer.list_plugins()
            if args.json:
                print(json.dumps(entries, indent=2, default=str, sort_keys=True))
            else:
                print(_format_plugin_inventory(entries))
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
            return 0
    except (
        PluginInstallationError,
        PluginPackageError,
        PluginRegistryError,
        PluginRuntimeError,
        OSError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 1


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
    lifecycle_store: PluginServiceLifecycleStore | None = None,
) -> int:
    """Print plugin service lifecycle status without changing plugin status output."""
    lifecycle_store = lifecycle_store or PluginServiceLifecycleStore()
    if plugin_id and service_code:
        rows = [lifecycle_store.get_service(plugin_id, service_code)]
    else:
        rows = [
            row
            for row in lifecycle_store.list_services()
            if plugin_id is None or row.plugin_id == plugin_id
        ]
    print(
        json.dumps(
            [row.__dict__ for row in rows], indent=2, default=str, sort_keys=True
        )
    )
    return 0


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
