-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Verify serialised production MLE hierarchy writes with isolated fixtures.
-- Usage: Approved DEV consumer SQLcl; setup, session A, session B, then cleanup.
-- Setup/cleanup explicitly COMMIT only reserved __MLE_CONC_ fixture records.
whenever sqlerror exit failure rollback
set define off
set serveroutput on
declare
  l_owner number;
  l_id number;
  l_parent number;
  l_version number;
  l_started number:=dbms_utility.get_time;
  l_waited number;
begin
  if user<>'ORAC_APX_PUB' or sys_context('userenv','con_name')<>'FREEPDB1' then raise_application_error(-20998,'Wrong DEV concurrency principal'); end if;
  select opening_id into l_owner from orac_chess.chess_opening_v where name='__MLE_CONC_ROOTS';
  orac_chess.chess_variation_api.save_variation(l_id,null,l_owner,null,null,null,'__MLE_CONC_ROOT_A','MAIN',to_clob('1.e4 *'),null,null,l_version);
  dbms_output.put_line('CHESS_MLE_LOCK_HELD');
end;
/
-- Start session B while A holds this transaction lock.
begin dbms_session.sleep(45); end;
/
commit;
prompt CHESS_MLE_SESSION_A_COMMITTED
exit
