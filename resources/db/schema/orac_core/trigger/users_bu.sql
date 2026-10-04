--liquibase formatted sql

--changeset clive:create_trigger_orac_core_trigger_users_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


create or replace trigger orac_core.users_bu
before update on orac_core.users
for each row
begin
  if lower(:new.username) = 'system'
     and lower(:old.username) <> 'system'
  then
    raise_application_error(
      -20076,
      'An ordinary user cannot be renamed to the reserved SYSTEM principal.'
    );
  end if;

  if lower(:old.username) = 'system'
     and (lower(:new.username) <> 'system' or :new.is_active <> 'N')
  then
    raise_application_error(
      -20075,
      'The reserved SYSTEM principal cannot be renamed or activated.'
    );
  end if;

  if :new.username <> trim(:new.username)
  then
    raise_application_error(-20058, 'Username must not contain surrounding whitespace.');
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

--rollback drop trigger orac_core.users_bu;
