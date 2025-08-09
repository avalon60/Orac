whenever sqlerror exit sql.sqlcode rollback
set define off verify off feedback off

alter session set container = FREEPDB1;

declare
  con varchar2(128) := sys_context('USERENV','CON_NAME');
begin
  if con <> 'FREEPDB1' then
    raise_application_error(-20000, 'Not in FREEPDB1 (in '||con||')');
  end if;
end;
/

-- Import (use @@ so it finds the file next to this script)
@@ORAC_workspace_export.sql
