#!/usr/bin/env bash
#------------------------------------------------------------------------------
# Author: Clive Bostock
#   Date: 16 December 2024
#   Name: setup.sh
#  Descr: Script to set up the application environment, including creating a
#         virtual environment, checking/installing pip, installing dependencies,
#         and configuring scripts. Determines Python interpreter based on the
#         system.
#         Optional: Unpacks Oracle Instant Client if -c option is used, and flattens.
#------------------------------------------------------------------------------

realpath() {
  if command -v readlink >/dev/null 2>&1; then
    readlink -f "$1"
  else
    cd "$(dirname "$1")" && pwd
  fi
}

# ---------------------------- New Variables ----------------------------
VENV_DIR=".venv"
step=0
PROG_PATH=$(realpath "$0")
APP_HOME=$(dirname "${PROG_PATH}")

BIN_DIR="bin"
UTILS_DIR="utils"
ORACLE_CLIENT_DIR="oracle_client"
CLIENT_ZIP=""

# ---------------------------- Parse Arguments ----------------------------
usage() {
  echo "Usage: $0 [-c <instant_client_zip>]"
  echo "  -c <zip>: Optional Oracle Instant Client ZIP to unpack"
  exit 1
}

while getopts "c:h" opt; do
  case "$opt" in
    c) CLIENT_ZIP="$OPTARG" ;;
    h) usage ;;
    *) usage ;;
  esac
done

# Exit on any error
set -e
pushd "${APP_HOME}"

# Step 0: Oracle Instant Client unzip (if specified)
if [[ -n "$CLIENT_ZIP" ]]; then
  echo "Step 0: Unpacking Oracle Instant Client from: $CLIENT_ZIP"

  if [[ ! -f "$CLIENT_ZIP" ]]; then
    echo "Error: ZIP file not found: $CLIENT_ZIP"
    exit 1
  fi

  echo "Unzipping Oracle Instant Client to: $ORACLE_CLIENT_DIR"
  rm -rf "$ORACLE_CLIENT_DIR"
  mkdir -p "$ORACLE_CLIENT_DIR"

  TMP_DIR=$(mktemp -d)
  unzip -q "$CLIENT_ZIP" -d "$TMP_DIR"

  INNER_DIR=$(find "$TMP_DIR" -maxdepth 1 -type d -name "instantclient_*" | head -n 1)
  if [[ -z "$INNER_DIR" ]]; then
    echo "Error: Could not find instantclient_* directory in extracted zip."
    rm -rf "$TMP_DIR"
    exit 1
  fi

  mv "$INNER_DIR"/* "$ORACLE_CLIENT_DIR"
  rm -rf "$TMP_DIR"

  echo "Instant Client unpacked and flattened into $ORACLE_CLIENT_DIR"
fi

# Continue with environment setup
source utils/utils.env
set_python

let step=${step}+1
step_desc="Check if pip is installed"
echo "Step ${step}: ${step_desc}..."

let step=${step}+1
step_desc="Create virtual environment if it doesn't exist"
echo "Step ${step}: ${step_desc}..."
$PYTHON -m venv "$VENV_DIR"
source_venv
ensure_pip

let step=${step}+1
step_desc="Activate the virtual environment"
echo "Step ${step}: ${step_desc}..."
VENV_PYTHON="${APP_HOME}/${VENV_DIR}/${SOURCE_DIR}/python"
if [ ! -x "$VENV_PYTHON" ]; then
  echo "Error: Python not found in the virtual environment. Exiting."
  exit 1
fi

echo "Upgrading pip..."
"$VENV_PYTHON" -m pip install --upgrade pip

let step=${step}+1
step_desc="Perform the packages install"
echo "Step ${step}: ${step_desc}..."
"$VENV_PYTHON" -m pip install .

let step=${step}+1
step_desc="Set executable permissions for shell script"
echo "Step ${step}: ${step_desc}..."
echo "Setting executable permissions for shell scripts..."
if [ -d "$BIN_DIR" ]; then
  chmod +x "$BIN_DIR"/*.sh
fi
if [ -d "$UTILS_DIR" ]; then
  chmod +x "$UTILS_DIR"/*.sh
fi

echo "Setup completed successfully!"
popd

