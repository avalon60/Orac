# Installation

This guide covers the supported local Orac deployment: a Linux host running the
Orac AI engine and a Docker Compose stack containing Oracle Database, ORDS/APEX,
and optional sidecar services.

## Prerequisites

- Linux host with `bash` and `sudo`.
- Docker Engine with a running daemon.
- Docker Buildx, used by `bin/orac-db-deploy.sh`.
- Python 3.12 or newer.
- Sufficient persistent disk space for Oracle data files.
- A local checkout of this repository.

The database deployment script currently supports only `TOPOLOGY=db-local`.
Remote Oracle deployments require a separately managed installation path.

## Install the Python Project

```bash
git clone https://github.com/Avalon60/orac.git
cd orac
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Poetry may be used for development and optional extras:

```bash
poetry install
```

## Configure the Stack Environment

Review `resources/config/orac.env`. The database deployment and control scripts
resolve this file and the Compose file relative to the Orac checkout.

Important values include:

```bash
COMPOSE_PROJECT_NAME=orac
ORAC_DB_CONTAINER_NAME=orac-db
CONTAINER_NAME=orac-db
ORADATA_DIR=/u01/orac-db/oradata
ORAC_IMAGE_NAME=orac
ORAC_IMAGE_TAG=latest
PORT_SQLNET=1521
PORT_HTTP=8042
PORT_EM=5500
TOPOLOGY=db-local
```

`PORT_HTTP` is the host port for ORDS/APEX. The container listens internally on
port `8080`.

## Prepare Persistent Oracle Storage

The default host data directory is `/u01/orac-db/oradata`. Change
`ORADATA_DIR` before deployment if another persistent location is required.

```bash
sudo mkdir -p /u01/orac-db/oradata
sudo chown -R 54321:54321 /u01/orac-db/oradata
```

The deployment script also creates and fixes ownership on the configured
directory. Deleting its contents destroys the local database state.

## Configure Database Credentials

Create the installer/provisioning connection named `orac`:

```bash
bin/dbconn-mgr.sh -c orac
```

For the default local deployment, enter:

- Username: `SYSTEM`
- Password: the Oracle administrator password
- DSN: normally `localhost:1521/FREEPDB1`
- Wallet ZIP: leave blank unless using a wallet

Credentials are encrypted under `~/.Orac/dsn_credentials.ini`.

Do not repurpose the `orac` installer connection as the least-privilege runtime
connection. Runtime connection names are configured separately in
`resources/config/orac.ini`.

Inspection commands:

```bash
bin/dbconn-mgr.sh -l
bin/dbconn-mgr.sh -e orac
```

## Configure Orac

Review `resources/config/orac.ini` before first startup. The complete reference
is [Configuration Parameters](configuration.md).

At minimum, confirm:

- the local LLM service, model, and URL
- database runtime connection names
- retrieval policy and SearXNG endpoint
- voice engines and local model paths
- optional display settings

## Deploy the Database

```bash
bin/orac-db-deploy.sh
```

The command:

- validates Docker, Buildx, the env file, and the local topology
- prepares `ORADATA_DIR`
- validates or creates the `orac` installer credential
- builds the Oracle image
- starts the database container
- installs Oracle Database objects, ORDS/APEX, and plugin database payloads
- waits for the `ORAC deployment complete` marker

Useful options:

```bash
bin/orac-db-deploy.sh --dry-run
bin/orac-db-deploy.sh --force
bin/orac-db-deploy.sh --force --no-cache
```

`--force` is destructive to deployment marker directories and replaces the
existing configured container. Review its output before confirming use.

## Start the Complete Stack

Database deployment does not start the host AI engine. After deployment:

```bash
bin/orac-ctl.sh compose-check
bin/orac-ctl.sh start
bin/orac-ctl.sh status
```

The operational stack consists of:

- Oracle Database
- ORDS/APEX
- the host Orac AI engine
- optional Compose profiles for SearXNG and Kokoro

Use `bin/orac.sh start` only when starting the AI engine independently.

## Verify the Installation

```bash
bin/orac-ctl.sh status
bin/orac-ctl.sh logs db
bin/orac-ctl.sh logs ai
```

Open the APEX administration application at:

```text
http://localhost:8042/ords/f?p=1042:LOGIN
```

Continue with:

- [APEX Administration](apex-administration.md)
- [Internet Retrieval](retrieval.md)
- [Voice Pipeline](voice-pipeline.md)
- [Home Assistant](../plugins/home_assistant/docs/home-assistant.md)
- [Docker Compose Deployment](docker-compose-deployment.md)
