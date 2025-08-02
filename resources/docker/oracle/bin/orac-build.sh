#!/usr/bin/env bash

# -------------------------------------------------------------
# orac-build.sh - Build Orac Docker Images (Linux-only)
# Author: Clive Bostock
# Date: 2025-07-18
# -------------------------------------------------------------

set -euo pipefail

# Default values
APEX_VERSION="24.1"
ORDS_VERSION="24.3.0.262.0924"
SQLCL_VERSION="25.2.1.195.1751"
ORAC_HOME="$(pwd)"
DOCKER_TAG_ORACLE="orac/dapex-xe:latest"
DOCKER_TAG_QDRANT="orac/qdrant:latest"
BASE_IMAGE_TAG_ORACLE="21.3.0"
QDRANT_IMAGE="qdrant/qdrant:latest" # Official Qdrant image
ORACLE_REGISTRY_USER=""
ORACLE_REGISTRY_TOKEN=""
BUILD_ARGS=""

# Usage function
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --oracle-user          Oracle Container Registry username (optional)"
    echo "  --oracle-token         Oracle Container Registry auth token (optional)"
    echo "  -a, --apex-version     Set Oracle APEX version (default: $APEX_VERSION)"
    echo "  -o, --ords-version     Set Oracle ORDS version (default: $ORDS_VERSION)"
    echo "  -s, --sqlcl-version    Set Oracle SQLcl version (default: $SQLCL_VERSION)"
    echo "  -d, --docker-tag       Docker image tag for Oracle (default: $DOCKER_TAG_ORACLE)"
    echo "  -h, --help             Show this help message and exit"
    echo
    echo "Example:"
    echo "  $0 --oracle-user clive --oracle-token abc123"
}

# Parse command-line options
while [[ $# -gt 0 ]]; do
    case "$1" in
        --oracle-user) ORACLE_REGISTRY_USER="$2"; shift 2 ;;
        --oracle-token) ORACLE_REGISTRY_TOKEN="$2"; shift 2 ;;
        -a|--apex-version) APEX_VERSION="$2"; shift 2 ;;
        -o|--ords-version) ORDS_VERSION="$2"; shift 2 ;;
        -s|--sqlcl-version) SQLCL_VERSION="$2"; shift 2 ;;
        -d|--docker-tag) DOCKER_TAG_ORACLE="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

# Check Docker daemon
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker daemon not running. Please start Docker and try again."
    exit 1
fi

# Oracle base image
BASE_IMAGE_ORACLE="container-registry.oracle.com/database/xe:${BASE_IMAGE_TAG_ORACLE}"

# Check if Oracle base image is cached locally
if ! docker image inspect "$BASE_IMAGE_ORACLE" >/dev/null 2>&1; then
    echo "🔍 Oracle XE base image not found locally: $BASE_IMAGE_ORACLE"

    # Prompt for Oracle credentials if not provided
    if [[ -z "$ORACLE_REGISTRY_USER" ]]; then
        read -rp "🔑 Enter Oracle Container Registry username: " ORACLE_REGISTRY_USER
    fi
    if [[ -z "$ORACLE_REGISTRY_TOKEN" ]]; then
        read -rsp "🔑 Enter Oracle Container Registry auth token: " ORACLE_REGISTRY_TOKEN
        echo
    fi

    # Login to Oracle Container Registry
    echo "🔐 Logging in to Oracle Container Registry..."
    echo "$ORACLE_REGISTRY_TOKEN" | docker login container-registry.oracle.com -u "$ORACLE_REGISTRY_USER" --password-stdin
else
    echo "📦 Oracle XE base image found locally."
fi

# Pull Qdrant image (anonymous pull from Docker Hub)
if ! docker image inspect "$QDRANT_IMAGE" >/dev/null 2>&1; then
    echo "🔍 Qdrant base image not found locally: $QDRANT_IMAGE"
    echo "📥 Pulling Qdrant base image from Docker Hub..."
    docker pull "$QDRANT_IMAGE"
else
    echo "📦 Qdrant base image found locally."
fi

# Build arguments for Oracle image
BUILD_ARGS+=" --build-arg APEX_VERSION=${APEX_VERSION}"
BUILD_ARGS+=" --build-arg ORDS_VERSION=${ORDS_VERSION}"
BUILD_ARGS+=" --build-arg SQLCL_VERSION=${SQLCL_VERSION}"
BUILD_ARGS+=" --build-arg ORAC_HOME=${ORAC_HOME}"

# Start Oracle Docker build
echo "🚀 Building Oracle Docker image: $DOCKER_TAG_ORACLE"
docker build \
    ${BUILD_ARGS} \
    -t "$DOCKER_TAG_ORACLE" \
    -f "$ORAC_HOME/resources/docker/oracle/Dockerfile" \
    "$ORAC_HOME/resources/docker/oracle"

echo "✅ Oracle image build complete: $DOCKER_TAG_ORACLE"

# Qdrant doesn’t require a custom build yet
echo "✅ Qdrant base image ready: $QDRANT_IMAGE"

