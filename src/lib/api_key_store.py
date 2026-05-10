"""Encrypted local API key store for Orac integrations."""
# Author: Clive Bostock
# Date: 2026-05-05
# Description: Provides encrypted API key lookup for local Orac integrations.

from __future__ import annotations

import configparser
from pathlib import Path

from lib.user_security import decrypted_user_credential
from lib.user_security import encrypted_user_credential


DEFAULT_API_KEY_STORE = Path("~/.Orac/api_keys.ini").expanduser()


class ApiKeyStoreError(RuntimeError):
  """Raised when an API key cannot be resolved."""


class ApiKeyStore:
  """Encrypted API key store backed by ``~/.Orac/api_keys.ini``."""

  def __init__(self, *, store_path: Path | None = None) -> None:
    """Create an API key store wrapper.

    Args:
      store_path (Path | None): Optional explicit key store path.
    """
    self.store_path = store_path or DEFAULT_API_KEY_STORE
    self.store_path.parent.mkdir(parents=True, exist_ok=True)
    if not self.store_path.exists():
      self.store_path.touch(mode=0o600)

  def get_api_key(self, resource_name: str) -> str:
    """Return the decrypted API key for a resource.

    Args:
      resource_name (str): Resource name, for example
        ``picovoice/access_key``.

    Returns:
      str: Decrypted API key.

    Raises:
      ApiKeyStoreError: If the key is missing or cannot be decrypted.
    """
    section = _normalise_resource_name(resource_name)
    config = self._read_config()
    if not config.has_section(section) or not config.has_option(section, "api_key"):
      raise ApiKeyStoreError(
        f"API key resource '{section}' is not configured in "
        f"{self.store_path}. Add it with: "
        f"PYTHONPATH=src poetry run python -m lib.api_key_store "
        f"--set {section}"
      )

    encrypted_value = config.get(section, "api_key")
    try:
      return decrypted_user_credential(encrypted_value)
    except Exception as exc:
      raise ApiKeyStoreError(
        f"API key resource '{section}' exists but could not be decrypted on "
        "this machine."
      ) from exc

  def set_api_key(self, resource_name: str, api_key: str) -> None:
    """Store an encrypted API key for a resource.

    Args:
      resource_name (str): Resource name.
      api_key (str): Plain text API key. This value is encrypted before
        storage and is never logged by this module.
    """
    section = _normalise_resource_name(resource_name)
    config = self._read_config()
    if not config.has_section(section):
      config.add_section(section)
    config.set(section, "api_key", encrypted_user_credential(api_key))
    with self.store_path.open("w", encoding="utf-8") as config_file:
      config.write(config_file)
    try:
      self.store_path.chmod(0o600)
    except OSError:
      pass

  def _read_config(self) -> configparser.ConfigParser:
    """Read the key store config file."""
    config = configparser.ConfigParser()
    config.read(self.store_path)
    return config


def _normalise_resource_name(resource_name: str) -> str:
  """Normalise a key resource name for config section lookup."""
  cleaned = resource_name.strip().strip("/")
  if not cleaned:
    raise ApiKeyStoreError("API key resource name must not be empty")
  return cleaned


def main() -> int:
  """Run a tiny API key store helper for local setup.

  Returns:
    int: Process exit code.
  """
  import argparse
  import getpass

  parser = argparse.ArgumentParser(
    prog="python -m lib.api_key_store",
    description="Store encrypted Orac API keys in ~/.Orac/api_keys.ini.",
  )
  parser.add_argument("--set", metavar="RESOURCE", help="Set one API key.")
  args = parser.parse_args()

  if not args.set:
    parser.print_help()
    return 2

  value = getpass.getpass(f"API key for {args.set}: ")
  if not value.strip():
    print("API key must not be empty.")
    return 2
  ApiKeyStore().set_api_key(args.set, value)
  print(f"Stored encrypted API key resource: {args.set}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
