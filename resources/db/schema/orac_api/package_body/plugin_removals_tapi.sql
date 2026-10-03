--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Enforces plugin removal and dedicated schema ownership invariants.

--changeset clive:create_plugin_removals_tapi_body context:core labels:core stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace package body orac_api.plugin_removals_tapi as
  procedure ins(p_row in out orac_api.plugin_removals_v%rowtype) is
  begin
    insert into orac_api.plugin_removals_v (removal_id, plugin_id, plugin_registry_id, knowledge_scope_id, plugin_version, manifest_hash, schema_disposition, database_identity, resource_inventory, confirmed_by)
    values (p_row.removal_id, p_row.plugin_id, p_row.plugin_registry_id, p_row.knowledge_scope_id, p_row.plugin_version, p_row.manifest_hash, p_row.schema_disposition, p_row.database_identity, p_row.resource_inventory, p_row.confirmed_by)
    returning row_version into p_row.row_version;
  end ins;

  procedure checkpoint(p_removal_id in varchar2, p_checkpoints in json,
    p_external_complete_yn in varchar2, p_files_complete_yn in varchar2,
    p_error_code in varchar2 default null, p_error_message in varchar2 default null) is
  begin
    update orac_api.plugin_removals_v
       set checkpoints = p_checkpoints,
           external_complete_yn = p_external_complete_yn,
           files_complete_yn = p_files_complete_yn,
           last_error_code = p_error_code, last_error_message = p_error_message
     where removal_id = p_removal_id and completed_on is null;
    if sql%rowcount <> 1
    then
      raise_application_error(-20071, 'Incomplete removal operation not found.');
    end if;
  end checkpoint;

  procedure complete(p_removal_id in varchar2) is
  begin
    update orac_api.plugin_removals_v
       set completed_on = systimestamp, last_error_code = null, last_error_message = null
     where removal_id = p_removal_id and completed_on is null
       and external_complete_yn = 'Y' and files_complete_yn = 'Y';
    if sql%rowcount <> 1
    then
      raise_application_error(-20072, 'Required plugin cleanup is incomplete.');
    end if;
  end complete;
end plugin_removals_tapi;
/
--rollback drop package body orac_api.plugin_removals_tapi;
