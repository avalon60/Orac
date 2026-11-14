--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 10-Nov-2026
-- Description: Add exact-prefix continuation children without changing existing edge semantics.
-- Purpose: Widen the variation edge contract while retaining every installed record.
-- Usage: Managed plugin deployment before comprehensive catalogue batches.
--changeset clive:orac_chess_variation_continuation_check context:plugin,prod labels:plugin stripComments:false endDelimiter:/
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(*) from all_tables where owner='ORAC_CHESS' and table_name='CHESS_VARIATION'
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints
  where owner='ORAC_CHESS' and constraint_name='CHS_VAR_CONTINUATION_CK';
  if l_count = 0
  then
    -- Add first so root/ownership/FEN shape is never unguarded.
    execute immediate q'~alter table orac_chess.chess_variation add constraint chs_var_continuation_ck check ((parent_variation_id is null and branch_ply is null and line_kind = 'MAIN') or (parent_variation_id is not null and branch_ply is not null and line_kind in ('ALTERNATIVE','CONTINUATION') and starting_fen is null))~';
  else
    -- An empty rollback retains support; safely recognise that exact existing check.
    select count(*) into l_count from all_constraints
    where owner='ORAC_CHESS' and constraint_name='CHS_VAR_CONTINUATION_CK'
      and table_name='CHESS_VARIATION' and status='ENABLED' and validated='VALIDATED'
      and lower(regexp_replace(search_condition_vc,'[[:space:]]','')) = '((parent_variation_idisnullandbranch_plyisnullandline_kind=''main'')or(parent_variation_idisnotnullandbranch_plyisnotnullandline_kindin(''alternative'',''continuation'')andstarting_fenisnull))';
    if l_count != 1
    then
      raise_application_error(-20014,'Existing continuation constraint differs from the approved contract.');
    end if;
  end if;
end;
/
-- Retain additive support and any valid user continuation rows on rollback.
--rollback empty

--changeset clive:orac_chess_variation_continuation_retire_narrow_check context:plugin,prod labels:plugin stripComments:false endDelimiter:/
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_VAR_CONTINUATION_CK' and status='ENABLED' and validated='VALIDATED'
declare
  l_count number;
begin
  select count(*) into l_count from all_constraints
  where owner='ORAC_CHESS' and constraint_name='CHS_VAR_BRANCH_CK';
  if l_count > 0
  then
    execute immediate 'alter table orac_chess.chess_variation drop constraint chs_var_branch_ck';
  end if;
end;
/
-- Restoring the narrow check could strand valid user continuations.
--rollback empty
