#!/usr/bin/env bash
##############################################################################
# Author: Clive Bostock
#   Date: 21 Wed 2025
#   Name: init-stage.sh
#  Descr: Performs an initialisation in edit mode, of the app project as an
#         extension to the BDDS platform.
##############################################################################
# Use a workaround for realpath if it's not available (e.g., on macOS)
realpath() {
  if command -v readlink >/dev/null 2>&1; then
    readlink -f "$1"
  else
    cd "$(dirname "$1")" && pwd
  fi
}

# Parse optional arguments
APP_REPO_DIR=""
while getopts ":a:" opt; do
  case ${opt} in
    a)
      APP_REPO_DIR="$OPTARG"
      ;;
    \?)
      echo "Usage: $0 [-a <app_repo_dir>]"
      exit 1
      ;;
  esac
done

# Resolve BDDS root directory
PROG_PATH=$(realpath "$0")
PROG_DIR=$(dirname "${PROG_PATH}")
APP_HOME=$(dirname "${PROG_DIR}")

# Resolve virtual environment location
if [ -d "${APP_HOME}/.venv" ]; then
  VENV_DIR="${APP_HOME}/.venv"
elif [ -d "${APP_HOME}/venv" ]; then
  VENV_DIR="${APP_HOME}/venv"
else
  VENV_DIR="${APP_HOME}/.venv"
fi

# Enter project directory
pushd "${APP_HOME}" || { echo "❌ Failed to switch to APP_HOME"; exit 1; }

# Source shared environment helpers
source "${APP_HOME}/utils/utils.env"

set_python
ensure_pip

# Create virtual environment if needed
if [ ! -d "${VENV_DIR}" ]; then
  $PYTHON -m venv "$VENV_DIR"
fi

echo "📁 App home: ${APP_HOME}"
source_venv

# Install BDDS in editable mode
echo "🔧 Installing BDDS in editable mode..."
${PYTHON} -m pip install -e .

# Optionally install app repo if supplied
if [ -n "$APP_REPO_DIR" ]; then
  if [ -d "$APP_REPO_DIR" ]; then
    echo "📦 Installing application repo in editable mode: $APP_REPO_DIR"
    ${PYTHON} -m pip install -e "$APP_REPO_DIR"
  else
    echo "⚠️  Application repo not found: $APP_REPO_DIR"
  fi
fi

