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
  begin
    orac_chess.chess_variation_api.save_variation(l_id,null,l_owner,null,null,null,'__MLE_CONC_ROOT_B','MAIN',to_clob('1.d4 *'),null,null,l_version);
    raise_application_error(-20999,'Concurrent competing_roots was incorrectly accepted');
  exception when others then if sqlcode<>-20009 then raise; end if; end;
  l_waited:=(dbms_utility.get_time-l_started)/100;
  if l_waited<3 then raise_application_error(-20999,'No lock wait observed; repeat coordinated run'); end if;
  rollback;
  dbms_output.put_line('CHESS_MLE_CONCURRENCY_PASSED wait_seconds='||l_waited);
end;
/
exit
