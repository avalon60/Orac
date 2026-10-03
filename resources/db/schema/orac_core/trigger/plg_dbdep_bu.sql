--liquibase formatted sql

--changeset clive:create_trigger_orac_core_trigger_plg_dbdep_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-03
-- __description__: maintain plugin_db_deployments update audit columns


create or replace trigger orac_core.plg_dbdep_bu
before insert or update on orac_core.plugin_db_deployments
for each row
declare
  l_removals number;
begin
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

--rollback drop trigger orac_core.plg_dbdep_bu;
