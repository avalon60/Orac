-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


create or replace trigger orac.users_bu
before update on orac.users
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
