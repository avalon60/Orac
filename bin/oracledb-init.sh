#!/usr/bin/env bash
################################################################################
# Author : Clive Bostock
# Date : 2025-08-01
# Purpose : Initialise and start the Orac database container.
################################################################################

set -e
PROG=$(basename "$0")
C="\c"
E="-e"

# Workaround for realpath if not available (e.g., on Mac)
realpath() {
  [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
}

# Directories and config
SCRIPT_DIR=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
ORAC_PROJECT_HOME=$(dirname "$SCRIPT_DIR")
BIN_DIR="${ORAC_PROJECT_HOME}/bin"
CONFIG_DIR="${ORAC_PROJECT_HOME}/resources/config"
ORA_DOCKER_DIR="${ORAC_PROJECT_HOME}/resources/docker/oracle"
CTL_DIR="${ORAC_PROJECT_HOME}/src/controller"
ENV_FILE="${CONFIG_DIR}/orac.env"
CREDENTIALS_FILE="${HOME}/.Orac/dsn_credentials.ini"

usage() {
  cat <<EOF
Usage: $PROG [options]

Initialise and start the Orac database container.

Options:
  -h, --help       Show this help message and exit
  -n, --dry-run    Show what would be done, without making changes
  -f, --force      Remove existing container before creating a new one. 
                   WARNING: This will destroy an existing Orac database.
      --no-cache   Build Docker image without using cache

Example:
  $PROG --force --no-cache
EOF
  exit 0
}

# Parse flags
DRY_RUN=0
FORCE=0
NO_CACHE=0

for arg in "$@"; do
  case $arg in
    --dry-run|-n) DRY_RUN=1 ;;
    --force|-f) FORCE=1 ;;
    --no-cache) NO_CACHE=1 ;;
    --help|-h) usage ;;
    *) echo "❌ Unknown option: $arg"
      usage ;;
  esac
done

# Load config
if [[ -f "$ENV_FILE" ]]; then
  source "$ENV_FILE"
else
  echo "❌ Environment file not found: $ENV_FILE"
  exit 1
fi

# Get Orac version
ORAC_VERSION=$(grep "__version__" "${CTL_DIR}/__init__.py" | cut -d'"' -f2)

echo "$PROG"
echo "Orac version: $ORAC_VERSION"
echo "🔧 Configuration loaded from: ${ENV_FILE}"
echo ""
echo "📋 Configuration:"
echo " CONTAINER_NAME : ${CONTAINER_NAME}"
echo " IMAGE_TAG : ${IMAGE_TAG}"
echo " ORADATA_DIR : ${ORADATA_DIR}"
echo " PORT_SQLNET : ${PORT_SQLNET}"
echo " PORT_HTTP : ${PORT_HTTP}"
echo " PORT_EM : ${PORT_EM}"
echo ""

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "🧪 Dry run mode enabled. No changes will be made."
  exit 0
fi

# Check Docker installed and running
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker not installed"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker daemon not running"
  exit 1
fi

# Handle existing container
if docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER_NAME$"; then
  if [[ "$FORCE" -eq 1 ]]
  then
    echo "♻️ Removing existing container: $CONTAINER_NAME"
    docker rm -f "$CONTAINER_NAME"
  else
    echo "⚠️ Container '$CONTAINER_NAME' already exists"
    echo " Use --force to remove and recreate it"
    exit 1
  fi
fi

if [[ "$FORCE" -eq 1 ]]
then
  echo "🧹 Cleaning up old Oracle config and Orac database data remnants..."
  sudo rm -f "${ORADATA_DIR}/.FREE.created" 
  sudo rm -fr "${ORADATA_DIR}/dbconfig"    
  sudo rm -fr "${ORADATA_DIR}/FREE"    
  # echo $E "Press RETURN to continue...$C"; read DUMMY

fi

# Ensure Oracle data directory
if [[ -d "${ORADATA_DIR}" ]]; then
  echo "📁 Oracle data directory exists: ${ORADATA_DIR}"
  CURRENT_OWNER=$(stat -c '%u' "${ORADATA_DIR}")
  if [[ "$CURRENT_OWNER" -ne 54321 ]]; then
    echo "⚠️ Ownership incorrect. Adjusting..."
    sudo chown -R 54321:54321 "${ORADATA_DIR}"
  fi
else
  echo "📁 Creating Oracle data directory..."
  sudo mkdir -p "${ORADATA_DIR}"
  sudo chown -R 54321:54321 "${ORADATA_DIR}"
fi

# Credential setup
if [[ ! -f "$CREDENTIALS_FILE" ]] || ! grep -q "^\[orac\]" "$CREDENTIALS_FILE"; then
  echo "🔐 Initializing credentials for 'orac'..."
  "${BIN_DIR}/dbconn-mgr.sh" -c orac
fi

# Retrieve password for ORACLE_PWD
ORACLE_PASSWORD=$("${BIN_DIR}/dbconn-property.sh" -n orac -p password)

# Rebuild image
pushd "$ORA_DOCKER_DIR" > /dev/null

echo "🔨 Building Docker image '${IMAGE_TAG}'..."
export ORACLE_PWD="$ORACLE_PASSWORD"

if [[ "$NO_CACHE" -eq 1 ]]
then
  docker buildx bake orac --no-cache --allow=fs.read=/home/clive/PycharmProjects/Orac
else
  docker buildx bake orac --allow=fs.read=/home/clive/PycharmProjects/Orac
fi

popd > /dev/null

# Run container
echo "🚀 Launching container '${CONTAINER_NAME}'..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT_SQLNET}:1521" \
  -p "${PORT_HTTP}:8080" \
  -p "${PORT_EM}:5500" \
  -e ORACLE_PWD="${ORACLE_PASSWORD}" \
  -v "${ORADATA_DIR}:/opt/oracle/oradata" \
  "${IMAGE_TAG}"

if [[ $? -eq 0 ]]; then
  echo "🎉 Container '${CONTAINER_NAME}' is up"
  echo "📡 SQL*Net on port ${PORT_SQLNET}"
  echo "🌐 APEX/ORDS on http://localhost:${PORT_HTTP}"
  echo "📂 DB files in: ${ORADATA_DIR}"
else
  echo "❌ Failed to start container"
  exit 1
fi
