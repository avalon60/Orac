#!/usr/bin/env bash
# Script to ...
#
# Use a workaround for realpath if it's not available (possibly not on Mac)
PROG=$(basename $0)
E="-e"
realpath() {
  [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
}
ENTRY_POINT="$(basename $0 .sh).py"
SCRIPT_DIR=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
PROJECT_DIR=$(dirname "${SCRIPT_DIR}")
BIN_DIR=${PROJECT_DIR}/bin
CTL_DIR=${PROJECT_DIR}/src/controller
ORAC_VERSION=$(grep "__version__" ${CTL_DIR}/__init__.py | cut -d'"' -f2)

CONTAINER_NAME="oracle-xe"

print_usage() {
  echo "${PROG}"
  echo $E "Orac version: ${ORAC_VERSION}\n"
  echo "Usage: $0 ..."
  exit 1
}


# Parse command-line options
while getopts ":d:p:n:h" opt
do
  case $opt in
    d) ORADATA_DIR="$OPTARG" ;;
    p) ORACLE_PASSWORD="$OPTARG" ;;
    n) CONTAINER_NAME="$OPTARG" ;;
    h) print_usage ;;
    \?) echo "Invalid option: -$OPTARG" >&2; print_usage ;;
    :) echo "Option -$OPTARG requires an argument." >&2; print_usage ;;
  esac
done

