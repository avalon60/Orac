--liquibase formatted sql

--changeset clive:create_trigger_orac_core_trigger_plg_inv_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: maintain plugin_invocations update audit columns


create or replace trigger orac_core.plg_inv_bu
before update on orac_core.plugin_invocations
for each row
begin
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

--rollback drop trigger orac_core.plg_inv_bu;
