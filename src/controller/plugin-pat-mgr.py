#!/usr/bin/env python3
"""Manage encrypted plugin personal access tokens for Orac."""
# Author: Clive Bostock
# Date: 05-Jun-2026
# Description: Maintains encrypted plugin personal access tokens in ~/.Orac/pat_vault.ini.
#
# Purpose: Manage encrypted plugin-scoped personal access tokens.
# Usage: bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token

from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_secret_vault import DEFAULT_PAT_VAULT_PATH
from model.plugin_secret_vault import PluginPatVaultStore
from model.plugin_secret_vault import PluginSecretVaultError

__author__ = "Clive Bostock"
__date__ = "05-Jun-2026"
__description__ = "Maintains encrypted plugin personal access tokens in ~/.Orac/pat_vault.ini."


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Manage encrypted Orac plugin personal access tokens.",
    )
    parser.add_argument("--plugin", help="Plugin id, for example home_assistant.")
    parser.add_argument(
        "--vault-path",
        default=str(DEFAULT_PAT_VAULT_PATH),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--plugins-dir",
        default="plugins",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive delete operations without prompting.",
    )
    parser.add_argument(
        "--reveal",
        action="store_true",
        help="Allow --get to print a decrypted token value.",
    )

    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument(
        "--set",
        nargs="?",
        const="",
        metavar="KEY",
        help="Create or update a plugin secret key. Defaults to the manifest default key.",
    )
    operation.add_argument(
        "--edit",
        nargs="?",
        const="",
        metavar="KEY",
        help="Edit an existing plugin secret key. Defaults to the manifest default key.",
    )
    operation.add_argument(
        "--delete-key",
        nargs="?",
        const="",
        metavar="KEY",
        help="Delete one plugin secret key. Defaults to the manifest default key.",
    )
    operation.add_argument(
        "--delete-plugin",
        action="store_true",
        help="Delete the entire plugin section from the PAT vault.",
    )
    operation.add_argument(
        "--list-plugins",
        action="store_true",
        help="List plugin sections configured in the PAT vault.",
    )
    operation.add_argument(
        "--list-keys",
        action="store_true",
        help="List key names configured for one plugin without values.",
    )
    operation.add_argument(
        "--list-expected",
        action="store_true",
        help="List manifest-declared secret keys for one plugin.",
    )
    operation.add_argument(
        "--check",
        nargs="?",
        const="",
        metavar="KEY",
        help="Return whether one plugin secret exists without revealing it.",
    )
    operation.add_argument(
        "--get",
        nargs="?",
        const="",
        metavar="KEY",
        help="Retrieve one decrypted plugin secret. Defaults to manifest default key. Requires --reveal.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the plugin PAT manager CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    store = PluginPatVaultStore(
        vault_path=Path(args.vault_path),
        plugins_dir=Path(args.plugins_dir),
    )

    try:
        return _run(args, store, parser)
    except PluginSecretVaultError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace, store: PluginPatVaultStore, parser: argparse.ArgumentParser) -> int:
    """Execute the selected operation."""
    if args.list_plugins:
        for plugin_id in store.list_plugins():
            print(plugin_id)
        return 0

    plugin_id = _required_plugin(args, parser)

    if args.set is not None:
        key = _selected_key(store, plugin_id, args.set)
        value = _prompt_secret(plugin_id, key)
        store.set_secret(plugin_id, key, value)
        print(f"Stored encrypted secret '{key}' for plugin '{plugin_id}'.")
        return 0

    if args.edit is not None:
        key = _selected_key(store, plugin_id, args.edit)
        value = _prompt_secret(plugin_id, key)
        store.edit_secret(plugin_id, key, value)
        print(f"Updated encrypted secret '{key}' for plugin '{plugin_id}'.")
        return 0

    if args.delete_key is not None:
        key = _selected_key(store, plugin_id, args.delete_key)
        if not _confirmed(args, f"delete secret '{key}' for plugin '{plugin_id}'"):
            print("Deletion cancelled.")
            return 2
        removed = store.delete_key(plugin_id, key)
        print(
            f"Deleted secret '{key}' for plugin '{plugin_id}'."
            if removed
            else f"Secret '{key}' was not configured for plugin '{plugin_id}'."
        )
        return 0

    if args.delete_plugin:
        if not _confirmed(args, f"delete all secrets for plugin '{plugin_id}'"):
            print("Deletion cancelled.")
            return 2
        removed = store.delete_plugin(plugin_id)
        print(
            f"Deleted all secrets for plugin '{plugin_id}'."
            if removed
            else f"No secrets were configured for plugin '{plugin_id}'."
        )
        return 0

    if args.list_keys:
        for key in store.list_keys(plugin_id):
            print(key)
        return 0

    if args.list_expected:
        expected = store.list_expected_keys(plugin_id)
        if not expected:
            print(f"Plugin '{plugin_id}' declares no expected PAT vault keys.")
            return 0
        for secret in expected:
            required = "required" if secret.required else "optional"
            print(f"{secret.key}\t{required}\t{secret.description}")
        return 0

    if args.check is not None:
        key = _selected_key(store, plugin_id, args.check)
        exists = store.check_secret(plugin_id, key)
        if exists:
            print(f"Secret '{key}' is configured for plugin '{plugin_id}'.")
            return 0
        print(f"Secret '{key}' is not configured for plugin '{plugin_id}'.")
        return 1

    if args.get is not None:
        key = _selected_key(store, plugin_id, args.get)
        if not args.reveal:
            print("Refusing to print decrypted secret without --reveal.", file=sys.stderr)
            return 2
        print(store.get_secret(plugin_id, key))
        return 0

    parser.error("No operation selected.")
    return 2


def _required_plugin(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    """Return the required plugin id or fail argument parsing."""
    if not args.plugin:
        parser.error("--plugin is required for this operation.")
    return str(args.plugin)


def _prompt_secret(plugin_id: str, key: str) -> str:
    """Prompt securely for a plugin secret value."""
    value = getpass.getpass(f"Secret for {plugin_id}.{key}: ")
    if not value.strip():
        raise PluginSecretVaultError("Secret value must not be empty.")
    return value


def _selected_key(store: PluginPatVaultStore, plugin_id: str, raw_key: str) -> str:
    """Return explicit key or the manifest default key."""
    if raw_key:
        return raw_key
    return store.default_key(plugin_id)


def _confirmed(args: argparse.Namespace, action: str) -> bool:
    """Return whether a destructive operation is confirmed."""
    if args.yes:
        return True
    answer = input(f"Confirm {action}? Type yes to continue: ")
    return answer.strip().lower() == "yes"


if __name__ == "__main__":
    raise SystemExit(main())
