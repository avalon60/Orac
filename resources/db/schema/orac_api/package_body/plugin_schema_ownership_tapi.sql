--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Privileged schema provisioning and removal receipts.

--changeset clive:create_plugin_schema_ownership_tapi_body context:core labels:core stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace package body orac_api.plugin_schema_ownership_tapi as
  procedure assert_provisioning_actor is
  begin
    -- Existing Docker administrative scripts execute as SYS. No execute grant
    -- is issued to CODE, ORAC, plugins or the APEX parsing schema.
    if sys_context('userenv', 'session_user') <> 'SYS'
    then
      raise_application_error(-20078, 'Schema ownership requires the privileged host provisioning path.');
    end if;
  end assert_provisioning_actor;

  procedure ins(p_row in out orac_api.plugin_schema_ownership_v%rowtype) is
    l_count number;
  begin
    assert_provisioning_actor;
    if p_row.schema_name in ('ORAC', 'ORAC_CORE', 'ORAC_API', 'ORAC_CODE', 'ORAC_PLUGIN', 'ORAC_APX_PUB', 'SYS', 'SYSTEM')
    then
      raise_application_error(-20079, 'Protected schemas cannot be plugin-owned.');
    end if;
    select count(*) into l_count
      from orac_api.plugin_registry_v plugin,
           json_table(plugin.database_schemas_summary, '$[*]' columns (schema_name varchar2(128) path '$')) declared
     where plugin.plugin_registry_id = p_row.plugin_registry_id
       and plugin.plugin_id = p_row.plugin_id
       and upper(declared.schema_name) = p_row.schema_name;
    if l_count <> 1
    then
      raise_application_error(-20079, 'Schema is not declared by the current plugin registration.');
    end if;
    insert into orac_api.plugin_schema_ownership_v (plugin_id, plugin_registry_id, database_identity, schema_name, database_user_id, database_user_created_on, provisioning_evidence)
    values (p_row.plugin_id, p_row.plugin_registry_id, p_row.database_identity, p_row.schema_name, p_row.database_user_id, p_row.database_user_created_on, p_row.provisioning_evidence)
    returning schema_ownership_id, row_version into p_row.schema_ownership_id, p_row.row_version;
  end ins;

  procedure record_disposition(p_schema_ownership_id in number, p_removal_id in varchar2,
    p_disposition in varchar2) is
    l_receipt orac_api.plugin_schema_ownership_v%rowtype;
    l_removal orac_api.plugin_removals_v%rowtype;
  begin
    assert_provisioning_actor;
    select * into l_receipt from orac_api.plugin_schema_ownership_v
     where schema_ownership_id = p_schema_ownership_id for update;
    select * into l_removal from orac_api.plugin_removals_v
     where removal_id = p_removal_id and completed_on is null;
    if l_receipt.plugin_registry_id <> l_removal.plugin_registry_id
       or l_receipt.plugin_id <> l_removal.plugin_id
       or l_receipt.database_identity <> l_removal.database_identity
       or p_disposition is null
       or p_disposition <> case l_removal.schema_disposition when 'KEEP' then 'RETAINED' else 'DROPPED' end
    then
      raise_application_error(-20079, 'Schema disposition does not match removal authorization.');
    end if;
    if l_receipt.disposition = p_disposition and l_receipt.removal_id = p_removal_id
    then
      return;
    end if;
    if l_receipt.disposition <> 'OWNED'
    then
      raise_application_error(-20079, 'Schema receipt is no longer current.');
    end if;
    update orac_api.plugin_schema_ownership_v
       set disposition = p_disposition, removal_id = p_removal_id
     where schema_ownership_id = p_schema_ownership_id;
  end record_disposition;
end plugin_schema_ownership_tapi;
/
--rollback drop package body orac_api.plugin_schema_ownership_tapi;
