--liquibase formatted sql

--changeset clive:create_trigger_orac_core_trigger_plg_apxapp_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: maintain plugin_apex_apps update audit columns

create or replace trigger orac_core.plg_apxapp_bu
before insert or update on orac_core.plugin_apex_apps
for each row
declare
  l_removals number;
begin
  if (inserting and :new.installation_receipt is not null)
     or updating('INSTALLATION_RECEIPT')
  then
    if sys_context('userenv', 'session_user') <> 'SYS' then
      raise_application_error(-20078, 'Only privileged installation may attest APEX ownership.');
    end if;
  end if;
  if updating and :old.installation_receipt is not null then
    if :new.plugin_id <> :old.plugin_id
       or :new.app_alias <> :old.app_alias
       or :new.workspace <> :old.workspace
       or :new.parsing_schema <> :old.parsing_schema
       or :new.installed_app_id is null
       or :new.installed_app_id <> :old.installed_app_id
    then
      raise_application_error(-20079, 'Receipted APEX application identity cannot change.');
    end if;
  end if;
  select count(*) into l_removals from orac_core.plugin_removals
   where plugin_id = :new.plugin_id and completed_on is null;
  if l_removals <> 0
  then
    raise_application_error(-20073, 'Plugin removal blocks operational registration changes.');
  end if;
  if updating
  then
    :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session', 'app_user'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version, 1) + 1;
  end if;
end;
/

--rollback drop trigger orac_core.plg_apxapp_bu;
