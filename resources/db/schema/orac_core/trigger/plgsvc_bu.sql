--liquibase formatted sql

--changeset clive:create_trigger_orac_core_trigger_plgsvc_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: maintain plugin_services update audit columns

create or replace trigger orac_core.plgsvc_bu
before insert or update on orac_core.plugin_services
for each row
declare
  l_owner_count number;
begin
  if :new.service_owner_type = 'PLUGIN'
  then
    select count(*)
      into l_owner_count
      from orac_core.plugin_registry plugin
     where plugin.plugin_registry_id = :new.plugin_registry_id
       and plugin.plugin_id = :new.plugin_id;

    if l_owner_count <> 1
    then
      raise_application_error(-20057, 'Plugin service owner does not match the registered plugin.');
    end if;
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

--rollback drop trigger orac_core.plgsvc_bu;
