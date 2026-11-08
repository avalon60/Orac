-- Author: Clive Bostock
-- Date: 02-Nov-2026
-- Purpose: Hold the common hierarchy lock during a concurrent opposite reparent.
-- Usage: Run after setup.sql, then start session_b.sql after CHESS_LOCK_HELD appears.
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on
set define off
declare
  l_a number;
  l_b number;
  l_version number;
begin
  if user!='SYSTEM' or sys_context('userenv','con_name')!='FREEPDB1' then raise_application_error(-20998,'Wrong concurrency test target'); end if;
  select opening_id into l_a from orac_chess.chess_opening_v where name='__ORAC_ADMIN_CONC_A' and row_version=1;
  select opening_id into l_b from orac_chess.chess_opening_v where name='__ORAC_ADMIN_CONC_B' and row_version=1;
  orac_chess.chess_admin_api.save_opening(l_a,1,'__ORAC_ADMIN_CONC_A','OPENING',null,l_b,l_version);
  dbms_output.put_line('CHESS_LOCK_HELD');
end;
/
begin dbms_session.sleep(45); end;
/
commit;
prompt CHESS_SESSION_A_COMMITTED
exit
