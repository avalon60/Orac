-- Author: Clive Bostock
-- Date: 02-Nov-2026
-- Purpose: Prove waiting writers re-read hierarchy and reject stale row versions.
-- Usage: Run while session_a.sql holds CHESS_LOCK_HELD; elapsed wait must exceed 3 seconds.
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on
set define off
declare
  l_a number;
  l_b number;
  l_version number;
  l_started number := dbms_utility.get_time;
  l_waited number;
begin
  if user!='SYSTEM' or sys_context('userenv','con_name')!='FREEPDB1' then raise_application_error(-20998,'Wrong concurrency test target'); end if;
  select opening_id into l_a from orac_chess.chess_opening_v where name='__ORAC_ADMIN_CONC_A';
  select opening_id into l_b from orac_chess.chess_opening_v where name='__ORAC_ADMIN_CONC_B';
  begin
    orac_chess.chess_admin_api.save_opening(l_b,1,'__ORAC_ADMIN_CONC_B','OPENING',null,l_a,l_version);
    raise_application_error(-20999,'Concurrent hierarchy cycle accepted');
  exception when others then
    if sqlcode!=-20004 then raise; end if;
  end;
  l_waited:=(dbms_utility.get_time-l_started)/100;
  if l_waited<3 then raise_application_error(-20999,'No lock wait observed; repeat coordinated run'); end if;
  begin
    orac_chess.chess_admin_api.save_opening(l_a,1,'__ORAC_ADMIN_CONC_A','OPENING',null,null,l_version);
    raise_application_error(-20999,'Stale post-wait version accepted');
  exception when others then
    if sqlcode!=-20001 then raise; end if;
  end;
  rollback;
  dbms_output.put_line('CHESS_CONCURRENCY_PASSED wait_seconds='||l_waited);
end;
/
exit
