# SQLcl Liquibase Database Deployment

Orac uses SQLcl Liquibase as the authoritative deployment mechanism for core
Orac database objects after bootstrap account creation.

## Deployment Paths

Docker image build installs SQLcl and copies Liquibase configuration only. The
Oracle database is not running during `docker build`, so Liquibase does not
apply database changes at image build time.

First-time container setup still uses dedicated SQL*Plus bootstrap scripts for
database services and account provisioning:

- APEX is installed by the existing setup scripts.
- ORDS is installed by the existing setup scripts.
- `ORAC_CORE`, `ORAC_API`, `ORAC_CODE`, `ORAC_APX_PUB`, `ORAC`,
  `ORAC_PLUGIN`, quotas, account-level grants, and bootstrap privileges are
  created by the existing user-creation scripts.
- core schema objects are probed, validated, and applied by
  `resources/docker/oracle/setup/040-orac-liquibase-deltas.sh`.
- APEX workspace and application exports are imported by
  `resources/docker/oracle/setup/045-orac-apex-import.sh` after core schema
  objects, grants, synonyms, and parsing-schema dependencies exist.
- APEX roles are initialised by
  `resources/docker/oracle/setup/050-init-app-role.sh`.

The first-setup order is:

```text
030/031 SQL*Plus schema user bootstrap
035 SQL*Plus non-Liquibase schema bundle runner
040 Liquibase tracking probe plus validate/update for core objects
045 SQL*Plus APEX workspace/app import
050 APEX role initialisation
998 final DB/APEX/ORDS completion checks
999 extended string support and current completion marker
```

On-demand core deltas use:

```text
resources/docker/oracle/bin/deploy-orac-db.sh
resources/db/liquibase/liquibase-core.properties
resources/db/schema/productController.xml
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

Core Orac deployment uses SQLcl Liquibase's default tracking table names in the
`SYSTEM` schema:

```text
databasechangelog
databasechangeloglock
```

Custom core tracking table names are not configured unless a documented
collision risk is proven. The core deployment wrapper runs a controlled
`validate`, `update-sql`, and `update` tracking probe before first-setup
deployment and fails if the configured tracking table names do not match the
observed tables SQLcl Liquibase actually uses.

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
SQL*Plus first-time setup path. Plugin APEX apps continue to use
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

Core tracking probe:

```bash
docker exec orac-db /home/oracle/orac/bin/deploy-orac-db.sh --probe-tracking
```

Existing developer database adoption:

```bash
docker exec orac-db /home/oracle/orac/bin/deploy-orac-db.sh --changelog-sync
```

The adoption path validates representative existing core objects and invalid
object state before running Liquibase `changelogSync`. Use it only for
developer databases that were already populated by the old SQL*Plus schema
bundle. Fresh installs must use normal `update` so Liquibase creates the
objects and changelog rows.

Core controller coverage checks:

```bash
poetry run python scripts/check_core_liquibase.py
poetry run pytest tests/test_check_core_liquibase.py
```

Plugin Liquibase dry run is normally invoked by the plugin installer after
payload validation and staging.

Liquibase is authoritative for core Orac database objects represented by
`resources/db/schema/productController.xml`, which is mirrored into the
container as `${ORAC_HOME}/schema/productController.xml`. Orac-owned APEX
exports live under `resources/db/apex`, are mirrored into the container as
`${ORAC_HOME}/apex`, and are imported by SQL*Plus only after the Liquibase
deployment succeeds. The SQL*Plus schema runner no longer runs Liquibase-owned
core object directories by default; set `RUN_CORE_OBJECTS_WITH_SQLPLUS=1` only
for an explicit legacy recovery run.
