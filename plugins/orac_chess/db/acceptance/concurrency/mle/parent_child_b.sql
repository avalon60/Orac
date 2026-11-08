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
  select opening_id into l_owner from orac_chess.chess_opening_v where name='__MLE_CONC_PARENT';
  select variation_id into l_parent from orac_chess.chess_variation_v where name='__MLE_CONC_MAIN' and opening_id=l_owner;
  select variation_id into l_id from orac_chess.chess_variation_v where name='__MLE_CONC_ALT' and opening_id=l_owner;
  begin
    orac_chess.chess_variation_api.save_variation(l_id,1,l_owner,null,l_parent,1,'__MLE_CONC_ALT','ALTERNATIVE',to_clob('1.e4 e6 *'),null,null,l_version);
    raise_application_error(-20999,'Concurrent parent_child was incorrectly accepted');
  exception when others then if sqlcode<>-20025 then raise; end if; end;
  l_waited:=(dbms_utility.get_time-l_started)/100;
  if l_waited<3 then raise_application_error(-20999,'No lock wait observed; repeat coordinated run'); end if;
  rollback;
  dbms_output.put_line('CHESS_MLE_CONCURRENCY_PASSED wait_seconds='||l_waited);
end;
/
exit
