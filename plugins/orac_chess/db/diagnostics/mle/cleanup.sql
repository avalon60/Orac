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
  l_conflicts pls_integer;
begin
  select count(*), count(case when object_type <> 'FUNCTION' then 1 end)
  into l_count, l_conflicts from dba_objects
  where owner = 'ORAC_CHESS' and object_name = 'CHESS_MLE_PROOF_RUN';
  if l_conflicts <> 0
  then
    raise_application_error(-20006, 'Conflicting proof object type: CHESS_MLE_PROOF_RUN');
  end if;
  if l_count > 0
  then
    execute immediate 'drop function orac_chess.chess_mle_proof_run';
  end if;
end;
/
declare
  l_count pls_integer;
  l_conflicts pls_integer;
begin
  select count(*), count(case when object_type <> 'FUNCTION' then 1 end)
  into l_count, l_conflicts from dba_objects
  where owner = 'ORAC_CHESS' and object_name = 'CHESS_MLE_PROOF_SMOKE';
  if l_conflicts <> 0
  then
    raise_application_error(-20006, 'Conflicting proof object type: CHESS_MLE_PROOF_SMOKE');
  end if;
  if l_count > 0
  then
    execute immediate 'drop function orac_chess.chess_mle_proof_smoke';
  end if;
end;
/
declare
  l_count pls_integer;
  l_conflicts pls_integer;
begin
  select count(*), count(case when object_type <> 'MLE ENVIRONMENT' then 1 end)
  into l_count, l_conflicts from dba_objects
  where owner = 'ORAC_CHESS' and object_name = 'CHESS_MLE_PROOF_ENV';
  if l_conflicts <> 0
  then
    raise_application_error(-20006, 'Conflicting proof object type: CHESS_MLE_PROOF_ENV');
  end if;
  if l_count > 0
  then
    execute immediate 'drop mle env orac_chess.chess_mle_proof_env';
  end if;
end;
/
declare
  l_count pls_integer;
  l_conflicts pls_integer;
begin
  select count(*), count(case when object_type <> 'MLE MODULE' then 1 end)
  into l_count, l_conflicts from dba_objects
  where owner = 'ORAC_CHESS' and object_name = 'CHESS_MLE_PROOF_BRIDGE';
  if l_conflicts <> 0
  then
    raise_application_error(-20006, 'Conflicting proof object type: CHESS_MLE_PROOF_BRIDGE');
  end if;
  if l_count > 0
  then
    execute immediate 'drop mle module orac_chess.chess_mle_proof_bridge';
  end if;
end;
/
declare
  l_count pls_integer;
  l_conflicts pls_integer;
begin
  select count(*), count(case when object_type <> 'MLE MODULE' then 1 end)
  into l_count, l_conflicts from dba_objects
  where owner = 'ORAC_CHESS' and object_name = 'CHESS_MLE_PROOF_POLICY';
  if l_conflicts <> 0
  then
    raise_application_error(-20006, 'Conflicting proof object type: CHESS_MLE_PROOF_POLICY');
  end if;
  if l_count > 0
  then
    execute immediate 'drop mle module orac_chess.chess_mle_proof_policy';
  end if;
end;
/
declare
  l_count pls_integer;
  l_conflicts pls_integer;
begin
  select count(*), count(case when object_type <> 'MLE MODULE' then 1 end)
  into l_count, l_conflicts from dba_objects
  where owner = 'ORAC_CHESS' and object_name = 'CHESS_MLE_PROOF_LIB';
  if l_conflicts <> 0
  then
    raise_application_error(-20006, 'Conflicting proof object type: CHESS_MLE_PROOF_LIB');
  end if;
  if l_count > 0
  then
    execute immediate 'drop mle module orac_chess.chess_mle_proof_lib';
  end if;
end;
/
prompt MLE_PROOF_CLEANUP_COMPLETE
