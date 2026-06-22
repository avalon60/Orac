--liquibase formatted sql

--changeset clive:create_trigger_orac_core_trigger_tmzone_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: maintain audit and row version columns on timezone updates

create or replace trigger orac_core.tmzone_bu
before update on orac_core.timezones
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
    sys_context('apex$session', 'app_user'),
    sys_context('userenv', 'proxy_user'),
    sys_context('userenv', 'session_user'),
    user
  );
  :new.row_version := nvl(:old.row_version, 0) + 1;
end;
/

--rollback drop trigger orac_core.tmzone_bu;
