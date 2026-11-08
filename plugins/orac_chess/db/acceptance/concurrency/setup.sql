-- Author: Clive Bostock
-- Date: 02-Nov-2026
-- Purpose: Create exactly two disposable DEV concurrency fixtures.
-- Usage: sql -name orac-db @plugins/orac_chess/db/acceptance/concurrency/setup.sql
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on
set define off
declare
  l_count number;
  l_id number;
  l_version number;
begin
  if user!='SYSTEM' or sys_context('userenv','con_name')!='FREEPDB1' then raise_application_error(-20998,'Wrong concurrency test target'); end if;
  select count(*) into l_count from orac_chess.chess_opening_v where name in ('__ORAC_ADMIN_CONC_A','__ORAC_ADMIN_CONC_B');
  if l_count!=0 then raise_application_error(-20999,'Fixture name collision; no data changed'); end if;
  orac_chess.chess_admin_api.save_opening(l_id,null,'__ORAC_ADMIN_CONC_A','OPENING',null,null,l_version);
  l_id:=null;
  orac_chess.chess_admin_api.save_opening(l_id,null,'__ORAC_ADMIN_CONC_B','OPENING',null,null,l_version);
  commit;
  dbms_output.put_line('CHESS_CONCURRENCY_FIXTURES_READY');
end;
/
exit
