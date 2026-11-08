-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Verify serialised production MLE hierarchy writes with isolated fixtures.
-- Usage: Approved DEV consumer SQLcl; setup, session A, session B, then cleanup.
-- Setup/cleanup explicitly COMMIT only reserved __MLE_CONC_ fixture records.
whenever sqlerror exit failure rollback
set define off
set serveroutput on
declare
  l_parent_owner number;
  l_root_owner number;
  l_root number;
  l_child number;
  l_version number;
  l_count number;
begin
  if user<>'ORAC_APX_PUB' or sys_context('userenv','con_name')<>'FREEPDB1' then raise_application_error(-20998,'Wrong DEV concurrency principal'); end if;
  select count(*) into l_count from orac_chess.chess_opening_v where name like '__MLE_CONC_%';
  if l_count<>0 then raise_application_error(-20999,'Concurrency fixture collision; inspect before cleanup'); end if;
  orac_chess.chess_admin_api.save_opening(l_parent_owner,null,'__MLE_CONC_PARENT','OPENING',null,null,l_version);
  orac_chess.chess_admin_api.save_opening(l_root_owner,null,'__MLE_CONC_ROOTS','OPENING',null,null,l_version);
  orac_chess.chess_variation_api.save_variation(l_root,null,l_parent_owner,null,null,null,'__MLE_CONC_MAIN','MAIN',to_clob('1.e4 e5 *'),null,null,l_version);
  orac_chess.chess_variation_api.save_variation(l_child,null,l_parent_owner,null,l_root,1,'__MLE_CONC_ALT','ALTERNATIVE',to_clob('1.e4 c5 *'),null,null,l_version);
end;
/
commit;
prompt CHESS_MLE_CONCURRENCY_SETUP_COMMITTED
exit
