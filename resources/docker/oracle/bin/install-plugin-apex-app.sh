#!/usr/bin/env bash
# Author: Clive Bostock
# Date: 20-Jun-2026
# Purpose: Import a plugin-supplied APEX application export into the configured workspace.
# Usage: install-plugin-apex-app.sh --plugin-id home_assistant --plugin-version 1.0.0 --app-alias ORAC_HA_STATUS --workspace ORAC --parsing-schema ORAC_APX_PUB --export /path/app.sql --entry-page-id 1

set -euo pipefail

PLUGIN_ID=""
PLUGIN_VERSION=""
APP_ALIAS=""
WORKSPACE=""
PARSING_SCHEMA=""
EXPORT_FILE=""
ENTRY_PAGE_ID=""
APPLICATION_ID=""
REPLACE_EXISTING="N"

usage() {
  sed -n '2,5p' "$0" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --plugin-id)
      PLUGIN_ID="${2:-}"
      shift 2
      ;;
    --plugin-version)
      PLUGIN_VERSION="${2:-}"
      shift 2
      ;;
    --app-alias)
      APP_ALIAS="${2:-}"
      shift 2
      ;;
    --workspace)
      WORKSPACE="${2:-}"
      shift 2
      ;;
    --parsing-schema)
      PARSING_SCHEMA="${2:-}"
      shift 2
      ;;
    --export)
      EXPORT_FILE="${2:-}"
      shift 2
      ;;
    --entry-page-id)
      ENTRY_PAGE_ID="${2:-}"
      shift 2
      ;;
    --application-id)
      APPLICATION_ID="${2:-}"
      shift 2
      ;;
    --replace-existing)
      REPLACE_EXISTING="Y"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

require_value() {
  local value="$1"
  local name="$2"
  if [[ -z "$value" ]]; then
    echo "Missing required argument: $name" >&2
    usage
    exit 2
  fi
}

require_identifier() {
  local value="$1"
  local name="$2"
  if [[ ! "$value" =~ ^[A-Za-z][A-Za-z0-9_]*$ ]]; then
    echo "$name must be a simple Oracle identifier" >&2
    exit 2
  fi
}

require_alias() {
  local value="$1"
  if [[ ! "$value" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]]; then
    echo "app alias must start with a letter and contain only letters, numbers, underscores and hyphens" >&2
    exit 2
  fi
}

require_number() {
  local value="$1"
  local name="$2"
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "$name must be a positive integer" >&2
    exit 2
  fi
}

require_value "$PLUGIN_ID" "--plugin-id"
require_value "$PLUGIN_VERSION" "--plugin-version"
require_value "$APP_ALIAS" "--app-alias"
require_value "$WORKSPACE" "--workspace"
require_value "$PARSING_SCHEMA" "--parsing-schema"
require_value "$EXPORT_FILE" "--export"
require_value "$ENTRY_PAGE_ID" "--entry-page-id"
require_alias "$APP_ALIAS"
require_identifier "$WORKSPACE" "--workspace"
require_identifier "$PARSING_SCHEMA" "--parsing-schema"
require_number "$ENTRY_PAGE_ID" "--entry-page-id"
if [[ -n "$APPLICATION_ID" ]]; then
  require_number "$APPLICATION_ID" "--application-id"
fi
if [[ ! -f "$EXPORT_FILE" ]]; then
  echo "APEX export does not exist: $EXPORT_FILE" >&2
  exit 2
fi

ORACLE_PDB="${ORACLE_PDB:-FREEPDB1}"

echo "Importing plugin APEX app ${APP_ALIAS} for plugin ${PLUGIN_ID} ${PLUGIN_VERSION}"
echo "Workspace=${WORKSPACE} Parsing schema=${PARSING_SCHEMA} PDB=${ORACLE_PDB}"

EXISTING_APP_ID=$(
  sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit failure rollback
set define off verify off feedback off heading off pagesize 0 serveroutput on size unlimited
alter session set container=${ORACLE_PDB};

declare
  l_application_id number;
begin
  select application_id
    into l_application_id
    from apex_applications
   where workspace = upper('${WORKSPACE}')
     and alias = upper('${APP_ALIAS}');
  dbms_output.put_line(l_application_id);
exception
  when no_data_found then
    null;
end;
/
SQL
)
EXISTING_APP_ID=$(printf '%s\n' "${EXISTING_APP_ID}" | sed '/^[[:space:]]*$/d' | tail -n 1)

if [[ -n "${EXISTING_APP_ID}" && "${REPLACE_EXISTING}" != "Y" ]]; then
  echo "APEX app alias ${APP_ALIAS} already exists in workspace ${WORKSPACE}; reusing application ${EXISTING_APP_ID}."
  echo "ORAC_PLUGIN_APEX_APP_ID=${EXISTING_APP_ID}"
  exit 0
fi

sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit failure rollback
set define off
set feedback on
set serveroutput on size unlimited
alter session set container=${ORACLE_PDB};

declare
  l_workspace_id number;
  l_existing_app_id number;
begin
  select workspace_id
    into l_workspace_id
    from apex_workspaces
   where workspace = upper('${WORKSPACE}');

  begin
    select application_id
      into l_existing_app_id
      from apex_applications
     where workspace = upper('${WORKSPACE}')
       and alias = upper('${APP_ALIAS}');
  exception
    when no_data_found then
      l_existing_app_id := null;
  end;

  apex_application_install.set_workspace_id(l_workspace_id);
  apex_util.set_security_group_id(l_workspace_id);
  apex_application_install.set_schema(upper('${PARSING_SCHEMA}'));
  apex_application_install.set_application_alias(upper('${APP_ALIAS}'));
  apex_application_install.set_application_name('${APP_ALIAS}');
  apex_application_install.set_auto_install_sup_obj(false);
  if '${APPLICATION_ID}' is not null then
    apex_application_install.set_application_id(to_number('${APPLICATION_ID}'));
  elsif l_existing_app_id is not null then
    apex_application_install.set_application_id(l_existing_app_id);
  else
    apex_application_install.generate_application_id;
  end if;
end;
/
@${EXPORT_FILE}
commit;
set serveroutput on size unlimited

declare
  l_application_id number;
begin
  select application_id
    into l_application_id
    from apex_applications
   where workspace = upper('${WORKSPACE}')
     and alias = upper('${APP_ALIAS}');
  dbms_output.put_line('ORAC_PLUGIN_APEX_APP_ID=' || l_application_id);
end;
/
SQL
