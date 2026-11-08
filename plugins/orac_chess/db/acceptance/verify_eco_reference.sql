-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Purpose: Verify complete ECO reference in an isolated approved installation.
-- Usage: As ORAC_CHESS run @plugins/orac_chess/db/acceptance/verify_eco_reference.sql
-- After clean installation and after upgrade from controller 12, run this script.
-- Repeat deployment must leave the ECO seed history entry at one execution.
-- Preservation: in an isolated owner transaction update one description, run the
-- packaged seed block without Liquibase metadata, assert the edited value survives,
-- then rollback. Never perform that rehearsal against shared or production data.
-- Failure atomicity: in an isolated schema add a failing insert trigger for E99,
-- execute the seed block against an empty reference, assert zero inserted rows and
-- no successful seed history entry, remove the trigger, and rerun deployment.
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on

declare
  l_count number;
  l_description clob;
begin
  if sys_context('userenv', 'session_user') != 'ORAC_CHESS'
  then
    raise_application_error(-20998, 'Requires isolated ORAC_CHESS owner session.');
  end if;
  select count(*) into l_count from orac_chess.chess_eco_code;
  if l_count != 500
  then
    raise_application_error(-20999, 'Expected 500 ECO codes.');
  end if;
  select count(*) into l_count
  from (
    select chr(64 + trunc((level - 1) / 100) + 1) ||
           to_char(mod(level - 1, 100), 'FM00') eco_code
    from dual connect by level <= 500
    minus
    select eco_code from orac_chess.chess_eco_code
  );
  if l_count != 0
  then
    raise_application_error(-20999, 'Missing ECO code.');
  end if;
  select count(*) into l_count from orac_chess.chess_eco_code
  where description is null or dbms_lob.getlength(description) = 0;
  if l_count != 0
  then
    raise_application_error(-20999, 'Empty reference description.');
  end if;
  for i in 25..29 loop
    select description into l_description
    from orac_chess.chess_eco_code where eco_code = 'C' || to_char(i, 'FM00');
    if dbms_lob.instr(l_description, 'Vienna') = 0
    then
      raise_application_error(-20999, 'Vienna family description missing.');
    end if;
  end loop;
  select count(*) into l_count from user_constraints
  where table_name = 'CHESS_ECO_CODE' and constraint_name in ('CHS_ECO_PK', 'CHS_ECO_CODE_CK')
    and status = 'ENABLED' and validated = 'VALIDATED';
  if l_count != 2
  then
    raise_application_error(-20999, 'Reference constraints missing or disabled.');
  end if;
  select count(*) into l_count from user_tab_privs_made
  where table_name = 'CHESS_ECO_CODE_V' and grantee = 'ORAC_APX_PUB'
    and privilege = 'SELECT' and grantable = 'NO';
  if l_count != 1
  then
    raise_application_error(-20999, 'Consumer view SELECT grant missing.');
  end if;
  select count(*) into l_count from user_tab_privs_made
  where table_name = 'CHESS_ECO_CODE' and grantee in ('PUBLIC', 'ORAC_APX_PUB', 'ORAC_PLUGIN');
  if l_count != 0
  then
    raise_application_error(-20999, 'Unexpected direct table grant.');
  end if;
  select count(*) into l_count from databasechangelog
  where id = 'orac_chess_eco_seed_2026_11_07' and author = 'clive'
    and exectype = 'EXECUTED';
  if l_count != 1
  then
    raise_application_error(-20999, 'Expected one successful once-only seed history row.');
  end if;
  dbms_output.put_line('ECO reference owner assertions passed.');
end;
/
-- Separately as ORAC_APX_PUB verify SELECT count(*) = 500 and Unicode names:
-- select count(*) from orac_chess.chess_eco_code_v;
-- select eco_code, description from orac_chess.chess_eco_code_v where eco_code='C25';
-- Direct SELECT from orac_chess.chess_eco_code must fail for ORAC_APX_PUB.
