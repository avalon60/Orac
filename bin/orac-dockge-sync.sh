#!/usr/bin/env bash
# Author  : Clive Bostock
# Date    : 31-May-2026
# Purpose : Mirror Orac's Compose stack into a Dockge-managed stack directory.
#
# Usage   : bin/orac-dockge-sync.sh [--target /opt/stacks/orac] [--dry-run]
#           bin/orac-dockge-sync.sh --include-oracle-password
#
# Notes   : Dockge is optional. This script copies Compose metadata so Dockge
#           can view/manage the stack without becoming an Orac dependency.

set -euo pipefail

PROG="$(basename "$0")"
realpath() { [[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"; }

SCRIPT_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

SOURCE_COMPOSE="${ORAC_DOCKGE_SOURCE_COMPOSE:-${PROJECT_DIR}/resources/docker/oracle/docker-compose.yaml}"
SOURCE_ENV="${ORAC_DOCKGE_SOURCE_ENV:-${PROJECT_DIR}/resources/config/orac.env}"
TARGET_DIR="${ORAC_DOCKGE_STACK_DIR:-/opt/stacks/orac}"
TARGET_COMPOSE_NAME="compose.yaml"
DRY_RUN=0
INCLUDE_ORACLE_PASSWORD=0

usage() {
  cat <<EOF
Usage: $PROG [--target DIR] [--dry-run|-n] [--include-oracle-password] [--help|-h]

Mirror Orac's Compose files into a Dockge stack directory.

Defaults:
  Source Compose : $SOURCE_COMPOSE
  Source env     : $SOURCE_ENV
  Target dir     : $TARGET_DIR

The target uses Dockge's conventional names:
  compose.yaml
  .env
  README.md

By default, ORACLE_PWD is not written to .env. Use --include-oracle-password
only if Dockge is expected to recreate the DB container and you accept storing
the database password in the Dockge stack env file.
EOF
}

require_file() {
  local path="$1"
  local description="$2"

  if [[ ! -f "$path" ]]; then
    echo "ERROR: Missing ${description}: $path" >&2
    return 1
  fi
}

run_write() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] %s\n' "$*"
    return 0
  fi

  "$@"
}

write_text_file() {
  local target="$1"
  local content="$2"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] write %s\n' "$target"
    return 0
  fi

  if [[ -w "$(dirname "$target")" ]]; then
    printf '%s\n' "$content" > "$target"
  else
    printf '%s\n' "$content" | sudo tee "$target" >/dev/null
  fi
}

copy_file() {
  local source="$1"
  local target="$2"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] copy %s -> %s\n' "$source" "$target"
    return 0
  fi

  if [[ -w "$(dirname "$target")" ]]; then
    cp "$source" "$target"
  else
    sudo cp "$source" "$target"
  fi
}

chmod_file() {
  local mode="$1"
  local target="$2"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] chmod %s %s\n' "$mode" "$target"
    return 0
  fi

  if [[ -w "$target" ]]; then
    chmod "$mode" "$target"
  else
    sudo chmod "$mode" "$target"
  fi
}

ensure_target_dir() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] mkdir -p %s\n' "$TARGET_DIR"
    return 0
  fi

  if [[ -d "$TARGET_DIR" ]]; then
    return 0
  fi

  if [[ -w "$(dirname "$TARGET_DIR")" ]]; then
    mkdir -p "$TARGET_DIR"
  else
    sudo mkdir -p "$TARGET_DIR"
  fi
}

oracle_password() {
  "${SCRIPT_DIR}/dbconn-property.sh" -n orac -p password
}

sync_stack() {
  local target_compose="${TARGET_DIR}/${TARGET_COMPOSE_NAME}"
  local target_env="${TARGET_DIR}/.env"
  local target_readme="${TARGET_DIR}/README.md"
  local readme
  local password

  require_file "$SOURCE_COMPOSE" "source Compose file"
  require_file "$SOURCE_ENV" "source env file"

  ensure_target_dir
  copy_file "$SOURCE_COMPOSE" "$target_compose"
  copy_file "$SOURCE_ENV" "$target_env"

  if [[ "$INCLUDE_ORACLE_PASSWORD" -eq 1 ]]; then
    password="$(oracle_password)"
    if [[ -z "$password" ]]; then
      echo "ERROR: Could not read Oracle password from Orac credential store." >&2
      return 1
    fi
    write_text_file "$target_env" "$(cat "$SOURCE_ENV")
ORACLE_PWD=${password}"
    chmod_file 600 "$target_env"
  else
    chmod_file 644 "$target_env"
  fi

  readme="Orac Dockge Stack
=================

This directory is a Dockge mirror of the Orac Compose stack.

Source Compose:
  $SOURCE_COMPOSE

Source env:
  $SOURCE_ENV

Generated with:
  $PROG

Dockge is optional. Orac scripts continue to call docker compose directly.

Use these settings when controlling Orac from the shell through this stack:

  ORAC_STACK_DIR=$TARGET_DIR
  ORAC_COMPOSE_FILE=$TARGET_DIR/$TARGET_COMPOSE_NAME
  ORAC_ENV_FILE=$TARGET_DIR/.env

Security note:
  ORACLE_PWD is not included by default. Without ORACLE_PWD, do not use Dockge
  to recreate the orac-db container. Use bin/orac-ctl.sh or run this sync script
  with --include-oracle-password only if you accept storing the DB password in
  this stack directory.
"
  write_text_file "$target_readme" "$readme"

  echo "Dockge stack mirror written:"
  echo "  $target_compose"
  echo "  $target_env"
  echo "  $target_readme"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --target)
      [[ "$#" -ge 2 ]] || { echo "ERROR: --target requires a directory." >&2; exit 1; }
      TARGET_DIR="$2"
      shift 2
      ;;
    --dry-run|-n)
      DRY_RUN=1
      shift
      ;;
    --include-oracle-password)
      INCLUDE_ORACLE_PASSWORD=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "${ORAC_DOCKGE_SYNC_LIB_ONLY:-0}" == "1" ]]; then
  return 0 2>/dev/null || exit 0
fi

sync_stack
