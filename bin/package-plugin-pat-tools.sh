#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 2026-06-23
# Description: Packages the plugin PAT manager and its source dependencies for reuse.
# Purpose: Create a portable source bundle for the plugin PAT vault tooling.
# Usage: bin/package-plugin-pat-tools.sh
# Example: bin/package-plugin-pat-tools.sh
set -euo pipefail

readonly ZIP_BUNDLE_NAME="plugin-pat-tools-bundle.zip"
readonly TAR_BUNDLE_NAME="plugin-pat-tools-bundle.tar.gz"

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

copy_required_file() {
  local relative_path="$1"
  local source_path="${PROJECT_DIR}/${relative_path}"
  local target_path="${STAGING_DIR}/${relative_path}"

  [[ -f "$source_path" ]] || fail "Required file is missing: ${relative_path}"
  mkdir -p "$(dirname "$target_path")"
  cp "$source_path" "$target_path"
}

write_minimal_config() {
  mkdir -p "${STAGING_DIR}/resources/config"
  cat >"${STAGING_DIR}/resources/config/orac.ini" <<'EOF'
[logging]
log_stamping = false
inc_stderr = false
log_level = INFO
EOF
}

write_requirements() {
  cat >"${STAGING_DIR}/requirements-plugin-pat-tools.txt" <<'EOF'
cryptography>=47.0.0,<48.0.0
loguru>=0.7.3,<0.8.0
packaging>=24.0,<27.0
EOF
}

write_plugin_routing_init() {
  mkdir -p "${STAGING_DIR}/src/model/plugin_routing"
  cat >"${STAGING_DIR}/src/model/plugin_routing/__init__.py" <<'EOF'
"""Minimal package marker for bundled plugin manifest discovery."""
# Author: Clive Bostock
# Date: 2026-06-23
# Description: Keeps the portable PAT bundle focused on manifest discovery imports.
EOF
}

write_readme() {
  cat >"${STAGING_DIR}/README.md" <<'EOF'
# Plugin PAT Tools Bundle

This bundle contains the Orac plugin personal access token (PAT) manager and the source files it needs to create, list, read, decrypt, and return plugin-scoped PAT values.

## Included files

- `bin/plugin-pat-mgr.sh`: shell wrapper for the PAT manager CLI.
- `src/controller/plugin-pat-mgr.py`: command-line interface for managing PAT entries.
- `src/model/plugin_secret_vault.py`: encrypted PAT vault store and plugin-facing scoped vault facade.
- `src/model/plugin_routing/discovery.py`: plugin manifest discovery and validation.
- `src/model/plugin_routing/models.py`: plugin manifest and secret metadata models.
- `src/model/plugin_routing/__init__.py`: generated minimal package marker for manifest discovery imports.
- `src/model/plugin_database_deployment.py`: protected schema constants used during manifest validation.
- `src/model/plugin_dependencies.py`: safe parsing for manifest-declared Python requirements.
- `src/lib/user_security.py`: AES-GCM encryption and decryption helpers.
- `src/lib/framework_errors.py`: shared exception type for unsupported platforms.
- `src/lib/fsutils.py`: project path and directory-name helpers.
- `src/lib/logutil.py`: logging decorator used by the encryption helper.
- `src/lib/config_mgr.py`: minimal configuration reader used by logging.
- `src/lib/icons.py`: icon constants imported by logging.
- `resources/config/orac.ini`: generated minimal logging config for portable use.
- `requirements-plugin-pat-tools.txt`: minimal Python package dependencies for this bundle.
- `LICENSE`: project licence, included when available.

No real vault files, user credential stores, caches, virtual environments, or build artefacts are included.

## What the tooling does

The PAT manager stores plugin-specific secret values in an encrypted local INI vault. It can:

- create or update a secret key for a plugin,
- list plugin sections in the vault,
- list configured keys for one plugin without revealing values,
- list expected keys declared by a plugin manifest,
- check whether a key exists,
- print a decrypted key only when explicitly asked with `--reveal`,
- delete a key or a whole plugin section.

The runtime-facing `PluginSecretVault` class gives plugin code a scoped `get()` method. Plugin code does not receive direct access to other plugin sections or to the wider store API.

## Where secrets are stored

By default, PAT entries are stored in:

```text
~/.Orac/pat_vault.ini
```

The manager creates the directory and vault file if needed, and applies restrictive permissions where the operating system supports them:

- `~/.Orac`: mode `0700`
- `~/.Orac/pat_vault.ini`: mode `0600`

You can override the path for testing or migration with `--vault-path`.

This bundle does not include:

- `~/.Orac/pat_vault.ini`
- `~/.Orac/api_keys.ini`
- `~/.Orac/dsn_credentials.ini`
- `.env` files
- any real credentials or secret stores

## How the vault works

The vault is an INI file. Each section is a plugin id, and each option in that section is a named secret key:

```text
[home_assistant]
access_token = <encrypted value>
refresh_token = <encrypted value>
```

Plugin ids and secret keys are validated before storage. By default, plugin ids are checked against plugin manifests in `plugins/`. A plugin manifest can declare:

- that it uses the `pat_vault`,
- its default secret key,
- whether custom keys are allowed,
- the known secret keys and setup hints.

## Encryption and decryption

Secret values are encrypted by `src/lib/user_security.py`.

At a high level:

- the plaintext secret is encrypted with AES-256-GCM,
- a random 16-byte salt is generated for each value,
- a random 12-byte IV is generated for each value,
- PBKDF2-HMAC-SHA256 derives the AES key,
- the stored value is base64 text containing salt, IV, tag, and ciphertext.

Unless a caller supplies a separate encryption password to the lower-level helper, the key material is derived from the local machine identifier:

- Linux: `/etc/machine-id`
- macOS: IOPlatformUUID from `ioreg`
- Windows: UUID from `Win32_ComputerSystemProduct`

## Portability limitation

Because the default encryption password is derived from the machine identifier, a vault encrypted on one machine is normally not decryptable on another machine. This is intentional, but it affects backup, restore, and handover.

For a work project, plan one of these approaches:

- create the PAT entries again on each target machine,
- migrate secrets through a proper secret manager,
- extend the tooling with an explicit, protected migration passphrase flow.

Do not copy `pat_vault.ini` to another machine and assume it will work.

## Requirements

Required Python version:

```text
Python >=3.12,<4.0
```

Install the minimal Python dependencies with:

```bash
python3 -m pip install -r requirements-plugin-pat-tools.txt
```

Python package dependencies:

- `cryptography>=47.0.0,<48.0.0`
- `loguru>=0.7.3,<0.8.0`
- `packaging>=24.0,<27.0`

Shell dependencies:

- POSIX-like shell environment with `bash`
- `python3`, `python`, or `py`
- optional `poetry`, if you want the wrapper to use a Poetry environment
- standard platform commands used for machine id detection:
  - Linux: `cat`
  - macOS: `ioreg` and `awk`
  - Windows: `powershell`

## Layout expectations

Run commands from the extracted bundle root or from a project root with the same layout:

```text
bin/plugin-pat-mgr.sh
src/controller/plugin-pat-mgr.py
src/model/...
src/lib/...
plugins/
```

The CLI validates plugin ids against manifests in `plugins/` by default. Use `--plugins-dir` if your manifests are elsewhere.

Each plugin manifest needs a matching plugin implementation directory with the same id. For example:

```text
plugins/home_assistant.json
plugins/home_assistant/
```

## Example commands

Create or update the default key declared by the plugin manifest:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --set
```

Create or update an explicit key:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token
```

List plugins that have vault sections:

```bash
bin/plugin-pat-mgr.sh --list-plugins
```

List configured keys for one plugin without values:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --list-keys
```

List manifest-declared expected keys:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --list-expected
```

Check whether a secret exists:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --check access_token
```

Read and decrypt a secret. This deliberately requires `--reveal`:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --get access_token --reveal
```

Delete one key:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --delete-key access_token
```

Delete one key without an interactive prompt:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --delete-key access_token --yes
```

Delete all vault entries for one plugin:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --delete-plugin
```

Use a non-default vault path:

```bash
bin/plugin-pat-mgr.sh --vault-path ./test-pat-vault.ini --plugin home_assistant --set access_token
```

Use a non-default plugin manifest directory:

```bash
bin/plugin-pat-mgr.sh --plugins-dir ./plugins --plugin home_assistant --list-expected
```

## Reading secrets from another Python script

Use the store when your script is trusted to name a plugin and key:

```python
from pathlib import Path
from model.plugin_secret_vault import PluginPatVaultStore

store = PluginPatVaultStore(
  vault_path=Path("~/.Orac/pat_vault.ini"),
  plugins_dir=Path("plugins"),
)

token = store.get_secret("home_assistant", "access_token")
```

Use the scoped facade when passing vault access into plugin code:

```python
from pathlib import Path
from model.plugin_secret_vault import PluginPatVaultStore
from model.plugin_secret_vault import PluginSecretVault

store = PluginPatVaultStore(plugins_dir=Path("plugins"))
vault = PluginSecretVault(plugin_id="home_assistant", store=store)

token = vault.get("access_token")
```

The scoped facade only exposes secrets for the plugin id it was created with.

## Security cautions

- Treat `--get --reveal` output as sensitive. It prints the decrypted token to stdout.
- Do not log decrypted values.
- Do not commit `pat_vault.ini` or any copied secret store.
- Do not include vault files in support bundles, backups, build artefacts, or test fixtures unless they are encrypted test-only fixtures with known dummy values.
- Use a dedicated PAT with least privilege for each plugin.
- Rotate tokens after accidental exposure.
- Use file permissions and operating-system account separation to protect `~/.Orac`.
- Prefer an organisation-approved secret manager for shared, production, or multi-machine use.

## Notes for reuse

This bundle is source-level tooling, not a full Orac runtime distribution. It depends on compatible plugin manifests for validation and on the local machine id for default decryption. If you change the manifest schema or secret policy in the target project, review `src/model/plugin_routing/discovery.py` and `src/model/plugin_secret_vault.py` together.
EOF
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly PROJECT_DIR

[[ -f "${PROJECT_DIR}/bin/plugin-pat-mgr.sh" ]] || fail "bin/plugin-pat-mgr.sh is missing"

STAGING_DIR="$(mktemp -d)"
readonly STAGING_DIR
trap 'rm -rf "$STAGING_DIR"' EXIT

readonly REQUIRED_FILES=(
  "bin/plugin-pat-mgr.sh"
  "src/controller/plugin-pat-mgr.py"
  "src/model/plugin_secret_vault.py"
  "src/model/plugin_routing/discovery.py"
  "src/model/plugin_routing/models.py"
  "src/model/plugin_database_deployment.py"
  "src/model/plugin_dependencies.py"
  "src/lib/user_security.py"
  "src/lib/framework_errors.py"
  "src/lib/fsutils.py"
  "src/lib/logutil.py"
  "src/lib/config_mgr.py"
  "src/lib/icons.py"
)

for relative_path in "${REQUIRED_FILES[@]}"; do
  copy_required_file "$relative_path"
done

if [[ -f "${PROJECT_DIR}/LICENSE" ]]; then
  copy_required_file "LICENSE"
fi

write_minimal_config
write_requirements
write_plugin_routing_init
write_readme

rm -f "${PROJECT_DIR}/${ZIP_BUNDLE_NAME}" "${PROJECT_DIR}/${TAR_BUNDLE_NAME}"

if command -v zip >/dev/null 2>&1; then
  (
    cd "$STAGING_DIR"
    zip -qr "${PROJECT_DIR}/${ZIP_BUNDLE_NAME}" .
  )
  printf '%s\n' "${PROJECT_DIR}/${ZIP_BUNDLE_NAME}"
else
  (
    cd "$STAGING_DIR"
    tar -czf "${PROJECT_DIR}/${TAR_BUNDLE_NAME}" .
  )
  printf '%s\n' "${PROJECT_DIR}/${TAR_BUNDLE_NAME}"
fi
