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
from pathlib import Path
import json
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_installer import PluginInstallationError
from model.plugin_installer import PluginInstaller
from model.plugin_package import PluginPackageError


def build_parser() -> argparse.ArgumentParser:
    """Build the plugin management argument parser."""
    parser = argparse.ArgumentParser(description="Package and install Orac plugins.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install one or more plugins.")
    source = install.add_mutually_exclusive_group(required=True)
    source.add_argument("archive", nargs="?", type=Path, help="Plugin .tar.gz package.")
    source.add_argument("--source", type=Path, help="Development plugin directory.")
    source.add_argument("--bundled", metavar="PLUGIN_ID", help="Bundled plugin id.")
    source.add_argument("--all", action="store_true", help="Install all bundled plugins.")
    install.add_argument(
        "--keep-failed-staging",
        action="store_true",
        help="Retain failed staging files for diagnosis.",
    )

    package = subparsers.add_parser("package", help="Build a plugin tarball.")
    package.add_argument("--source", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)

    status = subparsers.add_parser("status", help="Show registered plugin status.")
    status.add_argument("plugin_id")
    check = subparsers.add_parser("check", help="Validate registered plugin readiness.")
    check.add_argument("plugin_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the Orac plugin management CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    installer = PluginInstaller(keep_failed_staging=getattr(args, "keep_failed_staging", False))
    try:
        if args.command == "package":
            archive = installer.package(args.source, args.output)
            print(archive)
            print(f"sha256: {_sha256_file(archive)}")
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
    except (PluginInstallationError, PluginPackageError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 1


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a generated package."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
