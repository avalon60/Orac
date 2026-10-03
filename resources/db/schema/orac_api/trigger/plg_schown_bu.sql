--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Maintains immutable attribution and audit fields for plugin_schema_ownership.

--changeset clive:create_trigger_orac_api_plg_schown_bu context:core labels:core stripComments:false runOnChange:true splitStatements:false endDelimiter:/
create or replace trigger orac_api.plg_schown_bu
before update on orac_core.plugin_schema_ownership
for each row
begin
  if updating('PROVISIONING_EVIDENCE')
  then
    raise_application_error(-20070, 'Schema provisioning evidence is immutable.');
  end if;
  if :new.schema_ownership_id <> :old.schema_ownership_id
     or :new.schema_name <> :old.schema_name
     or :new.database_user_id <> :old.database_user_id
     or :new.database_user_created_on <> :old.database_user_created_on
     or :old.disposition = 'DROPPED'
     or (:old.disposition = 'RETAINED' and :new.disposition = 'OWNED')
  then
    raise_application_error(-20070, 'Schema incarnation and retired ownership are immutable.');
  end if;
  if :new.plugin_id <> :old.plugin_id or :new.plugin_registry_id <> :old.plugin_registry_id
     or :new.database_identity <> :old.database_identity
  then
    raise_application_error(-20070, 'Plugin lifecycle target attribution is immutable.');
  end if;
  :new.created_on := :old.created_on;
  :new.created_by := :old.created_by;
  :new.updated_on := systimestamp;
  :new.updated_by := sys_context('userenv', 'session_user');
  :new.row_version := :old.row_version + 1;
end;
/
--rollback drop trigger orac_api.plg_schown_bu;
