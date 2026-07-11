--liquibase formatted sql

--changeset clive:create_trigger_orac_core_prjreg_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: maintain project_registry update audit columns

create or replace trigger orac_core.prjreg_bu
before update on orac_core.project_registry
for each row
begin
  if nvl(:new.project_code, chr(0)) <> nvl(:old.project_code, chr(0))
  then
    raise_application_error(-20036, 'Project code cannot be changed.');
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

--rollback drop trigger orac_core.prjreg_bu;
