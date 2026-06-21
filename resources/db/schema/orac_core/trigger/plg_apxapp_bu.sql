-- __author__: clive
-- __date__: 2026-06-20
-- __description__: maintain plugin_apex_apps update audit columns

create or replace trigger orac_core.plg_apxapp_bu
before update on orac_core.plugin_apex_apps
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
