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

The default mode restores data into an already deployed schema set:

```bash
ORAC_RESTORE_CONTENT=data_only
ORAC_RESTORE_TABLE_EXISTS_ACTION=truncate
```

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
