#!/usr/bin/env bash
##############################################################################
# Author: Clive Bostock
#   Date: 16 Dec 2024 (A Merry Christmas to one and all! :o)
#   Name: build.sh
#  Descr: Performs a build and install of the project as packages.
##############################################################################
# Use a workaround for realpath if it's not available (possibly not on Mac)

realpath() {
  if command -v readlink >/dev/null 2>&1; then
    # Linux or systems where readlink is available
    readlink -f "$1"
  else
    # macOS or systems where readlink -f is not available
    cd "$(dirname "$1")" && pwd
  fi
}

PROG_PATH=$(realpath "$0")
PROG_DIR=$(dirname "${PROG_PATH}")
APP_HOME=$(dirname "${PROG_DIR}")
pushd "${APP_HOME}" || { echo "Failed to switch to APP_HOME"; exit 1; }
source utils/utils.env

set_python
# Ensure PIP is installed.
ensure_pip

if [ ! -d "${VENV_DIR}" ]
then
  $PYTHON -m venv "$VENV_DIR"
fi


echo "App home: ${APP_HOME}"
source_venv
${PYTHON} -m pip install . 
