-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Isolated DEV MLE feasibility proof; never included by plugin controllers.
-- Usage: SQLcl @plugins/orac_chess/db/diagnostics/mle/<script>.sql
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off
set sqlblanklines on
set serveroutput on
begin
  if sys_context('userenv','session_user') <> 'SYSTEM'
     or sys_context('userenv','con_name') <> 'FREEPDB1'
  then
    raise_application_error(-20000, 'Requires approved SYSTEM DEV FREEPDB1 connection');
  end if;
end;
/
declare
  l_count pls_integer;
begin
  select count(*) into l_count from dba_objects
  where owner = 'ORAC_CHESS' and object_name in ('CHESS_MLE_PROOF_LIB','CHESS_MLE_PROOF_POLICY','CHESS_MLE_PROOF_BRIDGE','CHESS_MLE_PROOF_ENV','CHESS_MLE_PROOF_RUN','CHESS_MLE_PROOF_SMOKE');
  if l_count <> 0
  then
    raise_application_error(-20001, 'Proof object collision: inspect DBA_OBJECTS; no replacements allowed');
  end if;
end;
/
