# Backup and Restore

Orac provides host-level backup and restore commands for the supported local
database topology.

## Create a Backup

```bash
bin/orac-backup.sh /path/to/backup-directory
```

The archive is named like:

```text
orac-backup-YYYYMMDD-HHMMSS.tar.gz
```

The default backup contains:

- Oracle Data Pump exports for Orac and deployed plugin schemas
- non-secret `resources/config/*.ini` files
- plugin metadata and versions
- exported, requested, and missing schema lists
- enabled foreign-key metadata
- `backup_manifest.json`

Missing manifest-declared plugin schemas are recorded and do not prevent other
schemas from being exported.

Useful options:

```bash
bin/orac-backup.sh --dry-run /tmp/orac-backups
bin/orac-backup.sh --skip-db /tmp/orac-backups
bin/orac-backup.sh --container orac-db --pdb FREEPDB1 /tmp/orac-backups
```

## Back Up One Plugin

List available manifest declarations without contacting Docker or the database:

```bash
bin/orac-backup.sh --list-plugins
```

The list includes disabled plugins and shows the exact ID, name, enabled flag,
declared schemas, backup-enabled schemas, and eligibility. It describes the
checkout's manifests; it does not establish that a plugin or schema is installed.

```bash
bin/orac-backup.sh --plugin orac_chess --dry-run /tmp/chess-backups
bin/orac-backup.sh --plugin orac_chess /tmp/chess-backups
bin/orac-restore.sh /tmp/chess-backups/orac-backup-YYYYMMDD-HHMMSS.tar.gz
```

`--plugin ID` matches one exact manifest ID and exports rows using Data Pump
`content=data_only`. It selects only that plugin's private `database.schemas`
entries whose `backup.include` is true (the default when omitted). Disabled
plugins remain eligible. Core schemas and schemas shared between manifests are
refused. Unknown or ambiguous IDs, plugins without eligible schemas, and any
missing selected schema fail without creating an archive. `--skip-db`,
`--include-vaults`, and `--export-vaults` cannot be combined with `--plugin`.

The archive retains the existing dump/log layout, selected schema lists,
foreign-key metadata, and selected plugin metadata. It excludes host config and
vaults. Its manifest adds `scope: plugin`, `plugin_id`, and
`database.content: data_only`. Full backups record `scope: full` and
`database.content: all`; archives without these fields retain those defaults.

The plugin's schemas **and tables must already be installed in the restore
target**, with definitions compatible with the exported rows. Install the
plugin through `bin/orac-plugin.sh install --bundled orac_chess` first if needed.
Rows-only archives cannot restore schema definitions; restore rejects
`ORAC_RESTORE_CONTENT=all` even with `--dry-run`. The normal `RECOVER`
confirmation, recovery API prerequisite, schema preflight, foreign-key handling,
recompilation, and invalid-object checks still apply. Plugin-only restores warn
about the selected plugin's version and leave the core plugin registry unchanged.
They do not quarantine plugin runtime state or report core table counts.

## Vault Handling

Vault files are excluded by default.

To copy allow-listed, machine-bound encrypted vault files unchanged:

```bash
bin/orac-backup.sh --include-vaults /tmp/orac-backups
```

To create a portable, passphrase-protected export:

```bash
bin/orac-backup.sh --export-vaults /tmp/orac-backups
```

For automation, provide only a secure passphrase file path:

```bash
export ORAC_VAULT_EXPORT_PASSPHRASE_FILE=/secure/path/orac-vault-passphrase
bin/orac-backup.sh --export-vaults /tmp/orac-backups
```

Do not put the passphrase itself in command arguments or environment variables.
`--include-vaults` and `--export-vaults` are mutually exclusive.

Machine-bound vault copies may not decrypt on another host. Portable exports
are stored under `vaults/portable/` in the archive.

## Restore Database Data

```bash
bin/orac-restore.sh /tmp/orac-backups/orac-backup-YYYYMMDD-HHMMSS.tar.gz
```

You can also point restore at a backup directory:

```bash
bin/orac-restore.sh /tmp/orac-backups
```

When given a directory, restore selects the newest direct
`orac-backup-*.tar.gz` archive by filename timestamp. It exits with an error if
the directory contains no matching backups.

Restore reads the selected archive manifest, reports version differences, and
requires the user to type `RECOVER` before import. It temporarily disables
relevant foreign keys, runs Data Pump import, and restores the constraints it
changed.

When restored plugin registry or plugin APEX app rows are present, restore
quarantines them before it reports success. Quarantined plugin rows are disabled
and marked as requiring reinstall, and plugin APEX app rows are made
non-launchable until the plugin lifecycle verifies the local package and imports
the APEX app into the current workspace.

For scratch recovery after recreating `orac-db`, use this order:

```bash
bin/orac-plugin.sh install --bundled home_assistant
bin/orac-restore.sh /tmp/orac-backups
bin/orac-plugin.sh install --all
bin/orac-plugin.sh check home_assistant
```

Use `bin/orac-plugin.sh install --all` before restore when you want to deploy
all bundled plugin schema objects recorded in the backup. Use
`bin/orac-plugin.sh install --bundled <plugin-id>` when you only need selected
plugin schemas, such as `home_assistant` for `ORAC_HA`.

Run plugin install again after restore so quarantined plugin registry and plugin
APEX app rows are verified against the local package and moved back to normal
installed/enabled state.

Plugin source files under `plugins/` are not enough for runtime readiness. The
plugin registry points Orac at activated snapshots under
`$ORAC_HOME/var/plugins/installed/<plugin-id>/<version>/`. If a restored or
stale registry row says a plugin is enabled but its `installed_path` is missing,
plugin routing and service startup can fail even though the bundled source
plugin still exists. Use `bin/orac-plugin.sh list` to review installed-artifact
health, and verify active plugins with `bin/orac-plugin.sh check <plugin-id>`
after restore or recovery work.

The default mode restores data into an already deployed schema set:

```bash
ORAC_RESTORE_CONTENT=data_only
ORAC_RESTORE_TABLE_EXISTS_ACTION=truncate
```

The default data-only mode requires the exported schemas and their tables to
already exist in the target database. Restore preflights manifest-exported
schemas before Data Pump import and reports missing plugin schema owners when it
can derive them from the backup manifest.

Supported data-only table actions are `skip`, `append`, and `truncate`.
`append` can create duplicate-key failures when rows already exist.

Full metadata replay is an advanced recovery mode:

```bash
ORAC_RESTORE_CONTENT=all \
ORAC_RESTORE_TABLE_EXISTS_ACTION=replace \
  bin/orac-restore.sh /path/to/archive.tar.gz
```

Use full metadata import only on a deliberately prepared target. Existing
users, packages, views, grants, and triggers can produce metadata conflicts.

## Current Vault Restore Limitation

The restore script does not currently import a portable vault export back into
`~/.Orac`. Retain the recovery passphrase and encrypted export for the future
vault recovery path.
