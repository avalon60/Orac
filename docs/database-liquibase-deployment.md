# SQLcl Liquibase Database Deployment

Orac supports SQLcl Liquibase for post-install and on-demand database deltas.
This path is deliberately separate from the first-time SQL*Plus setup path.

## Deployment Paths

Docker image build installs SQLcl and copies Liquibase configuration only. The
Oracle database is not running during `docker build`, so Liquibase does not
apply database changes at image build time.

First-time container setup still creates the base database through the existing
SQL*Plus path:

- APEX is installed by the existing setup scripts.
- ORDS is installed by the existing setup scripts.
- core schemas and APEX exports are installed by
  `resources/docker/oracle/setup/035-orac-schema_and_apps.sh`.
- APEX roles are initialised by
  `resources/docker/oracle/setup/038-init-app-role.sh`.
- migrated Liquibase deltas are validated and applied by
  `resources/docker/oracle/setup/040-orac-liquibase-deltas.sh`.

The first-setup order is:

```text
035 SQL*Plus schema/app install
038 APEX role initialisation
040 Liquibase validate/update for migrated deltas only
998 final DB/APEX/ORDS completion checks
999 extended string support and current completion marker
```

On-demand core deltas use:

```text
resources/docker/oracle/bin/deploy-orac-db.sh
resources/db/liquibase/liquibase-core.properties
resources/db/liquibase/changelogs/core/oracController.xml
```

Plugin-owned database deltas may opt in to Liquibase with manifest metadata:

```json
"database": {
  "deployment": {
    "type": "liquibase",
    "controller": "db/liquibase/pluginController.xml"
  }
}
```

Plugins that do not declare this continue to use the existing SQL*Plus plugin
database deployment path.

## Changelog Isolation

Core Orac deployment uses core-specific Liquibase tracking table names:

```text
orac_databasechangelog
orac_databasechangeloglock
```

Each plugin schema owns its own standard Liquibase tracking tables:

```text
databasechangelog
databasechangeloglock
```

This keeps plugin deployment history and locks separate from core deployment
history and from other plugins.

## Contexts And Labels

The initial context and label vocabulary is intentionally small:

- `core` for core Orac database deltas.
- `plugin` for plugin-owned database deltas.
- `dev`, `test`, and `prod` for environment targeting.
- `seed_data` for optional seed/reference data.
- `apex` is reserved; APEX imports are not part of ordinary Liquibase object
  deployment.

Default core deployment uses `core,prod` with label `core`. Plugin Liquibase
deployment uses `plugin,prod` with label `plugin`.

## Plugin Security Gate

Plugin Liquibase runs only after Orac-owned validation succeeds. Validation
checks plugin changelog XML and referenced SQL files before staging execution.
It rejects:

- protected Orac schema references;
- DDL outside manifest-declared plugin schemas;
- public synonyms;
- private synonyms into undeclared schemas;
- unauthorized grants;
- cross-plugin schema references;
- `includeAll` in plugin Liquibase changelogs;
- APEX assets inside plugin Liquibase deployment.

Plugin metadata updates remain Orac-owned. Plugin SQL and Liquibase changelogs
must not update core registry tables directly.

## APEX Boundary

APEX deployment remains separate. Core APEX workspace/app exports stay in the
existing first-time setup path. Plugin APEX apps continue to use
`install-plugin-apex-app.sh` and `apex_apps` manifest metadata.

Liquibase should manage database objects only unless a future technical review
approves an APEX-specific Liquibase path.

## Verification

Container checks:

```bash
docker exec orac-db sql -V
printf 'help liquibase\nexit\n' | docker exec -i orac-db sql /nolog
```

Core dry run:

```bash
docker exec orac-db /home/oracle/orac/bin/deploy-orac-db.sh --update-sql
```

Plugin Liquibase dry run is normally invoked by the plugin installer after
payload validation and staging.

Liquibase is not yet the authoritative full install mechanism. Full migration
from SQL*Plus to Liquibase is deferred until ordered real changesets exist.
