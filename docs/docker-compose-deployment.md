# Docker Compose Deployment

Docker Compose is the source of truth for Orac long-lived containerised
services.

Dockge is optional. Orac scripts call `docker compose` directly and do not
depend on Dockge.

## Stack Locations

Use one active stack directory per deployment:

- The default is `resources/docker/oracle`, resolved relative to the Orac base
  directory that contains `bin/orac-ctl.sh`.
- The default env file is `resources/config/orac.env`, resolved relative to
  the same Orac base directory.
- `/opt/orac/stack` is suitable for normal installed use when explicitly
  configured.
- `/opt/stacks/orac` is a suitable location for Dockge users.
- `resources/docker/oracle` can be used by developers when running from a
  repository checkout.

Configure the active stack with environment variables:

```bash
export ORAC_STACK_DIR=/opt/orac/stack
export ORAC_COMPOSE_FILE="$ORAC_STACK_DIR/docker-compose.yaml"
export ORAC_ENV_FILE="$ORAC_STACK_DIR/orac.env"
```

For repository development, no stack environment is required when running
`bin/orac-ctl.sh` from the checkout. The defaults resolve to the repository
paths. To be explicit:

```bash
export ORAC_STACK_DIR="$PWD/resources/docker/oracle"
export ORAC_COMPOSE_FILE="$ORAC_STACK_DIR/docker-compose.yaml"
export ORAC_ENV_FILE="$PWD/resources/config/orac.env"
```

## Dockge Mirror

Dockge expects stacks under `/opt/stacks/<stack-name>` and conventionally uses
`compose.yaml` plus `.env`. Orac keeps its source Compose file under
`resources/docker/oracle/docker-compose.yaml` and its env file under
`resources/config/orac.env`.

To make Orac visible in Dockge without making Dockge a dependency, mirror the
stack files:

```bash
bin/orac-dockge-sync.sh
```

This writes:

```text
/opt/stacks/orac/compose.yaml
/opt/stacks/orac/.env
/opt/stacks/orac/README.md
```

Then open Dockge and run `Scan Stacks Folder`.

By default, the mirror does not write `ORACLE_PWD` to `.env`. This is safer,
but means Dockge should not be used to recreate the `orac-db` container from
scratch. Use `bin/orac-ctl.sh` for normal Orac start/stop/restart, or run:

```bash
bin/orac-dockge-sync.sh --include-oracle-password
```

only if you explicitly accept storing the database password in
`/opt/stacks/orac/.env`.

To control Orac from the shell using the Dockge stack copy:

```bash
ORAC_STACK_DIR=/opt/stacks/orac \
ORAC_COMPOSE_FILE=/opt/stacks/orac/compose.yaml \
ORAC_ENV_FILE=/opt/stacks/orac/.env \
bin/orac-ctl.sh compose-check
```

## Services

The Compose stack defines these long-lived services:

- `orac-db`: core Oracle DB, ORDS, APEX, SQLcl service.
- `orac-kokoro`: optional Kokoro voice sidecar, controlled by profile `voice`.
- `orac-searxng`: optional SearXNG search sidecar, controlled by profile
  `search`.

Optional profiles are selected by `bin/orac-ctl.sh` from `resources/config/orac.ini`.

Kokoro profile activation:

- `tts_engine = kokoro`
- `tts_kokoro_autostart = true`
- `tts_kokoro_runtime = docker-cpu` or `docker-gpu`

When `tts_kokoro_runtime = external`, Orac does not start the Kokoro container.
It only checks the configured external readiness URL.

SearXNG profile activation:

- `internet_search_enabled = true`
- `default_search_provider = searxng`
- `retrieval.searxng.autostart = true`

The `orac-searxng` service mounts `./searxng/settings.yml` into the container
so SearXNG allows JSON output. Orac uses SearXNG's JSON endpoint; if
`search.formats` does not include `json`, searches fail with `403 Forbidden`.
The `searxng` directory must be deployed alongside the Compose file, for
example `/opt/stacks/orac/searxng/settings.yml` for Dockge or
`/opt/orac/stack/searxng/settings.yml` for a normal installed stack.

## Environment Variables

The stack env file should define deployment-specific values such as:

```bash
COMPOSE_PROJECT_NAME=orac
ORAC_DB_CONTAINER_NAME=orac-db
ORAC_IMAGE_NAME=orac
ORAC_IMAGE_TAG=latest
ORADATA_DIR=/u01/orac-db/oradata
PORT_SQLNET=1521
PORT_HTTP=8042
PORT_EM=5500
KOKORO_IMAGE=ghcr.io/remsky/kokoro-fastapi-cpu:latest
KOKORO_CONTAINER_NAME=orac-kokoro
KOKORO_HOST=127.0.0.1
KOKORO_PORT=8880
SEARXNG_IMAGE=searxng/searxng:latest
SEARXNG_CONTAINER_NAME=orac-searxng
SEARXNG_HOST=127.0.0.1
SEARXNG_PORT=8888
SEARXNG_SECRET=orac-local-searxng-change-me
```

Do not store `ORACLE_PWD` in the stack env file. `bin/orac-ctl.sh` reads it
from the existing Orac credential store and exports it only for the Compose
command invocation.

## Control Commands

Validate the active stack without changing Docker state:

```bash
bin/orac-ctl.sh compose-check
```

Start Orac:

```bash
bin/orac-ctl.sh start
```

Stop Orac:

```bash
bin/orac-ctl.sh stop
```

Tail logs:

```bash
bin/orac-ctl.sh logs db
bin/orac-ctl.sh logs voice
bin/orac-ctl.sh logs search
bin/orac-ctl.sh logs ai
```

## Database Provisioning

Use `bin/orac-db-deploy.sh` for initial local DB provisioning or an explicit
forced rebuild. It is a provisioning script, not the normal lifecycle command.

The script uses the same stack resolution model as `bin/orac-ctl.sh`:

```bash
bin/orac-db-deploy.sh --check-prereqs
bin/orac-db-deploy.sh
```

For a non-default stack location:

```bash
ORAC_STACK_DIR=/opt/stacks/orac \
ORAC_COMPOSE_FILE=/opt/stacks/orac/docker-compose.yaml \
ORAC_ENV_FILE=/opt/stacks/orac/orac.env \
bin/orac-db-deploy.sh
```

The deploy script prepares the host `ORADATA_DIR`, checks credentials, builds
the Orac DB image, starts the `orac-db` Compose service, and watches the DB
bootstrap log markers.

`--force` is destructive by design and is reserved for intentional rebuilds.
For Compose-managed containers it uses `docker compose stop orac-db` and
`docker compose rm -f orac-db`. For legacy non-Compose containers it removes
the named DB container only when `--force` is supplied.

## Migration Checks

Before migrating an existing `orac-db` container, run:

```bash
bin/orac-ctl.sh compose-check
```

The check reports the active stack directory, Compose file, env file, selected
profiles, Compose config validity, and current `orac-db` metadata where Docker
can inspect it.

Review differences in image, ports, mounts, environment, restart policy, and
health check before stopping an existing non-Compose-managed container. Do not
change `ORADATA_DIR`, delete volumes, or run `docker compose down -v` as part
of migration.

## Container Management Rule

Long-lived Orac service containers must be defined in Compose. Shell scripts
may call `docker compose`, inspect health, wait for readiness, and tail logs.
They must not create long-lived Orac service containers with `docker run`.

Temporary diagnostic or one-off maintenance containers are the only exception.
