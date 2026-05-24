#!/usr/bin/env python3
# Author: Clive Bostock
# Date: 20-May-2026
# Description: Exports selected Orac vault files into a portable encrypted bundle.
"""Export Orac local vaults using a recovery passphrase.

The helper decrypts values from the current machine-bound Orac vault files
using the existing ``lib.user_security`` primitives, then encrypts the
portable export payload with a caller-supplied recovery passphrase. Secret
values are never printed.
"""

from __future__ import annotations

import argparse
import configparser
from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
import sys

from lib.user_security import decrypted_user_credential
from lib.user_security import encrypted_user_credential


EXPORT_FORMAT_VERSION = 1
ENCRYPTION_DESCRIPTION = "orac_user_security_aes_256_gcm_pbkdf2_sha256"
SECRET_OPTIONS_BY_FILE: dict[str, set[str]] = {
    "dsn_credentials.ini": {"username", "password"},
    "api_keys.ini": {"api_key"},
}


def _read_passphrase_from_stdin() -> str:
    """Read a recovery passphrase from stdin.

    Returns:
        str: Non-empty recovery passphrase.

    Raises:
        ValueError: If stdin does not provide a non-empty passphrase.
    """
    passphrase = sys.stdin.readline().rstrip("\n")
    if not passphrase:
        raise ValueError("Vault export passphrase must not be empty.")
    return passphrase


def _read_passphrase_from_file(path: Path) -> str:
    """Read the first line of a recovery passphrase file.

    Args:
        path (Path): Passphrase file path.

    Returns:
        str: Non-empty recovery passphrase.

    Raises:
        ValueError: If the file is missing, unreadable, or empty.
    """
    if not path.exists():
        raise ValueError(f"Passphrase file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Passphrase path is not a file: {path}")

    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
    except IndexError as exc:
        raise ValueError("Passphrase file first line must not be empty.") from exc
    except OSError as exc:
        raise ValueError(f"Passphrase file is not readable: {path}") from exc

    if not first_line:
        raise ValueError("Passphrase file first line must not be empty.")
    return first_line


def _read_config_file(path: Path) -> configparser.ConfigParser:
    """Read an INI vault file.

    Args:
        path (Path): Vault file path.

    Returns:
        configparser.ConfigParser: Parsed vault file.
    """
    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    return config


def _export_vault_file(path: Path) -> dict[str, object]:
    """Export one allow-listed vault file.

    Args:
        path (Path): Vault file path.

    Returns:
        dict[str, object]: Plaintext export representation.
    """
    secret_options = SECRET_OPTIONS_BY_FILE[path.name]
    config = _read_config_file(path)
    sections: list[dict[str, object]] = []

    for section_name in config.sections():
        options: dict[str, str] = {}
        encrypted_options: list[str] = []
        for option_name, option_value in config.items(section_name):
            if option_name in secret_options:
                options[option_name] = decrypted_user_credential(option_value)
                encrypted_options.append(option_name)
            else:
                options[option_name] = option_value

        sections.append(
            {
                "name": section_name,
                "encrypted_options": encrypted_options,
                "options": options,
            }
        )

    return {
        "filename": path.name,
        "sections": sections,
    }


def export_vaults(
    *,
    vault_dir: Path,
    output_dir: Path,
    filenames: list[str],
    passphrase: str,
) -> None:
    """Create a portable encrypted vault export.

    Args:
        vault_dir (Path): Source vault directory.
        output_dir (Path): Destination directory.
        filenames (list[str]): Allow-listed filenames to export.
        passphrase (str): Recovery passphrase.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_files: list[dict[str, object]] = []

    for filename in filenames:
        source_path = vault_dir / filename
        if source_path.exists():
            exported_files.append(_export_vault_file(source_path))

    payload = {
        "format_version": EXPORT_FORMAT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": exported_files,
    }
    payload_json = json.dumps(payload, indent=2, sort_keys=True)
    encrypted_payload = encrypted_user_credential(
        payload_json,
        encryption_password=passphrase,
    )

    envelope = {
        "format_version": EXPORT_FORMAT_VERSION,
        "encryption": ENCRYPTION_DESCRIPTION,
        "ciphertext": encrypted_payload,
    }
    (output_dir / "vault_export.json.enc").write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "format_version": EXPORT_FORMAT_VERSION,
        "generated_at_utc": payload["generated_at_utc"],
        "encryption": ENCRYPTION_DESCRIPTION,
        "files": [item["filename"] for item in exported_files],
        "secret_values_included": True,
    }
    (output_dir / "vault_export_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        argparse.ArgumentParser: Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="orac_vault_export.py",
        description="Export selected Orac vault files as a portable encrypted bundle.",
    )
    parser.add_argument("--vault-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--files", nargs="+", required=True)
    passphrase_group = parser.add_mutually_exclusive_group(required=True)
    passphrase_group.add_argument("--passphrase-stdin", action="store_true")
    passphrase_group.add_argument("--passphrase-file", type=Path)
    return parser


def main() -> int:
    """Run the vault export command.

    Returns:
        int: Process exit code.
    """
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.passphrase_stdin:
            passphrase = _read_passphrase_from_stdin()
        else:
            passphrase = _read_passphrase_from_file(args.passphrase_file)

        export_vaults(
            vault_dir=args.vault_dir.expanduser(),
            output_dir=args.output_dir,
            filenames=args.files,
            passphrase=passphrase,
        )
    except Exception as exc:
        print(f"Portable vault export failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
