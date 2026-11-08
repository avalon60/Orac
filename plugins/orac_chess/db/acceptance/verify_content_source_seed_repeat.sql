-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Purpose: Prove the actual insert-only seed preserves source edits within a rolled-back transaction.
-- Usage: sql -name orac-db @plugins/orac_chess/db/acceptance/verify_content_source_seed_repeat.sql
-- Requires an approved dedicated DEV admin session after managed deployment.
-- Temporarily edits ChessVibes through the public API, reruns the exact seed SQL and rolls back.
-- No DDL, COMMIT, creator rename or video write is performed.
whenever sqlerror exit sql.sqlcode rollback
set define off
set serveroutput on
set autocommit off
variable source_seed_version number

declare
  l_version number;
begin
  if user != 'SYSTEM' or sys_context('userenv','con_name') != 'FREEPDB1' then
    raise_application_error(-20998,'Requires the approved dedicated DEV admin connection.');
  end if;
  savepoint content_source_seed_acceptance;
  select row_version into l_version from orac_chess.chess_content_source_v
  where creator='ChessVibes';
  orac_chess.chess_admin_api.save_content_source(
    'ChessVibes',l_version,'ChessVibes','__SEED_REPEAT_AUTHOR__',
    to_clob('__SEED_REPEAT_NOTES__'),:source_seed_version);
end;
/
@@../schema/seed_data/chess_content_source.sql

declare
  l_count number;
begin
  select count(*) into l_count from orac_chess.chess_content_source_v
  where creator='ChessVibes' and author='__SEED_REPEAT_AUTHOR__'
    and dbms_lob.compare(notes,to_clob('__SEED_REPEAT_NOTES__'))=0
    and row_version=:source_seed_version;
  if l_count != 1 then
    raise_application_error(-20999,'Repeating the actual source seed overwrote user edits or version.');
  end if;
  rollback to content_source_seed_acceptance;
  dbms_output.put_line('Content source seed repeat passed; original source values restored by rollback.');
exception when others then
  rollback;
  raise;
end;
/
