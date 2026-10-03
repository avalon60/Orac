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
if [[ ! "$PLUGIN_ID" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "plugin ID must be a canonical plugin identifier" >&2
  exit 2
fi
if [[ ! "$EXPORT_FILE" =~ ^/[A-Za-z0-9_./-]+$ ]]; then
  echo "export path must be a safe absolute staged path" >&2
  exit 2
fi
require_alias "$APP_ALIAS"
require_identifier "$WORKSPACE" "--workspace"
require_identifier "$PARSING_SCHEMA" "--parsing-schema"
require_number "$ENTRY_PAGE_ID" "--entry-page-id"
if [[ -n "$APPLICATION_ID" ]]; then
  require_number "$APPLICATION_ID" "--application-id"
  case "$APPLICATION_ID" in
    1042|1043|10042)
      echo "Core APEX application IDs cannot be installed by plugins" >&2
      exit 2
      ;;
  esac
fi
if [[ ! -f "$EXPORT_FILE" ]]; then
  echo "APEX export does not exist: $EXPORT_FILE" >&2
  exit 2
fi

ORACLE_PDB="${ORACLE_PDB:-FREEPDB1}"
require_identifier "$ORACLE_PDB" "ORACLE_PDB"

echo "Importing plugin APEX app ${APP_ALIAS} for plugin ${PLUGIN_ID} ${PLUGIN_VERSION}"
echo "Workspace=${WORKSPACE} Parsing schema=${PARSING_SCHEMA} PDB=${ORACLE_PDB}"

EXISTING_APP_ID=$(
  sqlplus -L -s / as sysdba <<SQL
whenever sqlerror exit failure rollback
set define off verify off feedback off heading off pagesize 0 serveroutput on size unlimited
alter session set container=${ORACLE_PDB};
set serveroutput on size unlimited

declare
  l_application_id number;
  l_registry_id number;
  l_workspace_id number;
  l_count number;
  l_database_identity varchar2(256);
  l_receipt json;
begin
  select plugin_registry_id into l_registry_id from orac_code.plugin_registry_v
   where plugin_id = '${PLUGIN_ID}' and removal_id is null;
  select installation_receipt into l_receipt from orac_api.plugin_apex_apps_v
   where plugin_id = '${PLUGIN_ID}' and upper(app_alias) = upper('${APP_ALIAS}')
     and upper(workspace) = upper('${WORKSPACE}')
     and upper(parsing_schema) = upper('${PARSING_SCHEMA}');
  select to_char(dbid) || ':' || rawtohex(guid) || ':' || name
    into l_database_identity from v\$pdbs
   where con_id = to_number(sys_context('userenv', 'con_id'))
     and name = upper('${ORACLE_PDB}') and open_mode = 'READ WRITE';
  select workspace_id into l_workspace_id from apex_workspaces
   where workspace = upper('${WORKSPACE}');
  apex_util.set_security_group_id(l_workspace_id);
  begin
    select application_id into l_application_id from apex_applications
     where workspace = upper('${WORKSPACE}') and alias = upper('${APP_ALIAS}');
  exception when no_data_found then l_application_id := null;
  end;
  if l_application_id is not null then
    apex_application.g_flow_id := l_application_id;
    select count(*) into l_count from dual
     where json_value(l_receipt, '$.plugin_registry_id' returning number) = l_registry_id
       and json_value(l_receipt, '$.application_id' returning number) = l_application_id
       and json_value(l_receipt, '$.database_identity') = l_database_identity
       and json_value(l_receipt, '$.workspace_id' returning number) = l_workspace_id
       and json_value(l_receipt, '$.marker') = apex_app_setting.get_value('ORAC_INSTALL_RECEIPT');
    if l_count <> 1 then
      raise_application_error(-20079, 'Existing APEX application has no matching ownership receipt.');
    end if;
    if '${APPLICATION_ID}' is not null and l_application_id <> to_number('${APPLICATION_ID}') then
      raise_application_error(-20079, 'Declared APEX application ID changed.');
    end if;
    dbms_output.put_line(l_application_id);
  elsif l_receipt is not null then
    raise_application_error(-20079, 'Receipted APEX application is missing; recovery is required.');
  end if;
  if '${APPLICATION_ID}' is not null then
    select count(*) into l_count from apex_applications
     where application_id = to_number('${APPLICATION_ID}')
       and (l_application_id is null or application_id <> l_application_id);
    if l_count <> 0 then
      raise_application_error(-20079, 'Declared APEX application ID is already occupied.');
    end if;
  end if;
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
set serveroutput on size unlimited

declare
  l_workspace_id number;
  l_existing_app_id number;
  l_registry_id number;
  l_database_identity varchar2(256);
  l_receipt json;
  l_count number;
begin
  select plugin_registry_id into l_registry_id from orac_code.plugin_registry_v
   where plugin_id = '${PLUGIN_ID}' and removal_id is null;
  select installation_receipt into l_receipt from orac_api.plugin_apex_apps_v
   where plugin_id = '${PLUGIN_ID}' and upper(app_alias) = upper('${APP_ALIAS}')
     and upper(workspace) = upper('${WORKSPACE}')
     and upper(parsing_schema) = upper('${PARSING_SCHEMA}');
  select to_char(dbid) || ':' || rawtohex(guid) || ':' || name
    into l_database_identity from v\$pdbs
   where con_id = to_number(sys_context('userenv', 'con_id'))
     and name = upper('${ORACLE_PDB}') and open_mode = 'READ WRITE';
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
  if nvl(l_existing_app_id, -1) <> nvl(to_number('${EXISTING_APP_ID}'), -1) then
    raise_application_error(-20079, 'APEX application changed after preflight.');
  end if;
  if l_existing_app_id is not null then
    apex_application.g_flow_id := l_existing_app_id;
    select count(*) into l_count from dual
     where json_value(l_receipt, '$.plugin_registry_id' returning number) = l_registry_id
       and json_value(l_receipt, '$.application_id' returning number) = l_existing_app_id
       and json_value(l_receipt, '$.database_identity') = l_database_identity
       and json_value(l_receipt, '$.workspace_id' returning number) = l_workspace_id
       and json_value(l_receipt, '$.marker') = apex_app_setting.get_value('ORAC_INSTALL_RECEIPT');
    if l_count <> 1 then
      raise_application_error(-20079, 'APEX ownership changed after preflight.');
    end if;
  elsif l_receipt is not null then
    raise_application_error(-20079, 'Receipted APEX application is missing.');
  end if;
  if '${APPLICATION_ID}' is not null then
    select count(*) into l_count from apex_applications
     where application_id = to_number('${APPLICATION_ID}')
       and (l_existing_app_id is null or application_id <> l_existing_app_id);
    if l_count <> 0 then
      raise_application_error(-20079, 'Declared APEX application ID became occupied.');
    end if;
  end if;
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
  l_registry_id number;
  l_workspace_id number;
  l_database_identity varchar2(256);
  l_marker varchar2(32) := rawtohex(sys_guid());
  l_receipt json;
  l_alias varchar2(128);
begin
  select application_id
    into l_application_id
    from apex_applications
   where workspace = upper('${WORKSPACE}')
     and alias = upper('${APP_ALIAS}');
  select plugin_registry_id into l_registry_id from orac_code.plugin_registry_v
   where plugin_id = '${PLUGIN_ID}' and removal_id is null;
  select app_alias into l_alias from orac_api.plugin_apex_apps_v
   where plugin_id = '${PLUGIN_ID}' and upper(app_alias) = upper('${APP_ALIAS}');
  select workspace_id into l_workspace_id from apex_workspaces
   where workspace = upper('${WORKSPACE}');
  select to_char(dbid) || ':' || rawtohex(guid) || ':' || name
    into l_database_identity from v\$pdbs
   where con_id = to_number(sys_context('userenv', 'con_id'))
     and name = upper('${ORACLE_PDB}') and open_mode = 'READ WRITE';
  apex_util.set_security_group_id(l_workspace_id);
  apex_application.g_flow_id := l_application_id;
  apex_app_setting.set_value('ORAC_INSTALL_RECEIPT', l_marker, true);
  select json_object('plugin_registry_id' value l_registry_id,
                     'application_id' value l_application_id,
                     'workspace_id' value l_workspace_id,
                     'database_identity' value l_database_identity,
                     'marker' value l_marker returning json)
    into l_receipt from dual;
  orac_api.plugin_apex_apps_tapi.record_installation_receipt(
    '${PLUGIN_ID}', l_alias, l_application_id, l_receipt);
  commit;
  dbms_output.put_line('ORAC_PLUGIN_APEX_APP_ID=' || l_application_id);
end;
/
SQL
