--liquibase formatted sql

--changeset clive:create_trigger_orac_core_users_bd context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-10-03
-- __description__: protect the reserved system preference principal

create or replace trigger orac_core.users_bd
before delete on orac_core.users
for each row
begin
  if lower(:old.username) = 'system'
  then
    raise_application_error(-20076, 'The reserved SYSTEM principal cannot be deleted.');
  end if;
end;
/

--rollback drop trigger orac_core.users_bd;
