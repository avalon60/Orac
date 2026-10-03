--liquibase formatted sql

--changeset clive:create_trigger_orac_core_trigger_plgreg_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-07
-- __description__: maintain plugin_registry update audit columns

create or replace trigger orac_core.plgreg_bu
before update on orac_core.plugin_registry
for each row
declare
  l_removals number;
begin
  select count(*) into l_removals from orac_core.plugin_removals
   where plugin_registry_id = :old.plugin_registry_id and completed_on is null;
  if l_removals > 0
  then
    raise_application_error(-20073, 'Plugin removal is incomplete; resume removal before changing registration.');
  end if;
  if nvl(:new.plugin_id, chr(0)) <> nvl(:old.plugin_id, chr(0))
     or :new.knowledge_scope_id <> :old.knowledge_scope_id
  then
    raise_application_error(-20047, 'Plugin identifier and current knowledge scope cannot be changed.');
  end if;

  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('apex$session', 'app_user'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version, 1) + 1;
end;
/

--rollback drop trigger orac_core.plgreg_bu;
