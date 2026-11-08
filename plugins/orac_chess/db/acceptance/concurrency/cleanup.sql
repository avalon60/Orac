-- Author: Clive Bostock
-- Date: 02-Nov-2026
-- Purpose: Remove only the two precisely identified concurrency fixture rows.
-- Usage: sql -name orac-db @plugins/orac_chess/db/acceptance/concurrency/cleanup.sql
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on
set define off
declare
  l_a number;
  l_b number;
  l_av number;
  l_bv number;
begin
  if user!='SYSTEM' or sys_context('userenv','con_name')!='FREEPDB1' then raise_application_error(-20998,'Wrong concurrency cleanup target'); end if;
  select opening_id,row_version into l_a,l_av from orac_chess.chess_opening_v where name='__ORAC_ADMIN_CONC_A';
  select opening_id,row_version into l_b,l_bv from orac_chess.chess_opening_v where name='__ORAC_ADMIN_CONC_B';
  orac_chess.chess_admin_api.delete_opening(l_a,l_av);
  orac_chess.chess_admin_api.delete_opening(l_b,l_bv);
  commit;
  dbms_output.put_line('CHESS_CONCURRENCY_FIXTURES_REMOVED');
end;
/
exit
