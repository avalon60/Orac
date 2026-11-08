-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Purpose: Verify direct ECO save, preservation, validation and clear semantics.
-- Usage: As ORAC_CHESS in an isolated approved DEV installation, run
-- @plugins/orac_chess/db/acceptance/verify_eco_assignments.sql
-- Fixtures are rolled back. This is not an install, upgrade or browser test.
whenever sqlerror exit sql.sqlcode rollback
set define off
set serveroutput on

declare
  l_opening number;
  l_gambit number;
  l_variation number;
  l_game number;
  l_game_version number;
  l_missing_code varchar2(3);
  l_opening_version number;
  l_gambit_version number;
  l_variation_version number;
  l_new_version number;
  l_count number;
  l_name varchar2(200) := '__ECO_CHECK_' || sys_context('userenv', 'sessionid');
  procedure expect_count(p_actual number, p_expected number, p_message varchar2) is
  begin
    if p_actual != p_expected then
      raise_application_error(-20999, p_message || ': expected ' || p_expected || ', got ' || p_actual);
    end if;
  end;
begin
  savepoint eco_acceptance;
  if user != 'ORAC_CHESS' or sys_context('userenv','con_name') != 'FREEPDB1' then
    raise_application_error(-20998, 'Use an isolated approved ORAC_CHESS DEV session.');
  end if;
  select count(*) into l_count from user_objects
  where object_name in ('CHESS_GAMBIT_ECO','CHESS_VARIATION_ECO','CHESS_GAMBIT_ECO_V','CHESS_VARIATION_ECO_V') and status='VALID';
  expect_count(l_count,4,'ECO tables and views are valid');
  select count(*) into l_count from user_objects
  where object_name in ('CHESS_ADMIN_TAPI','CHESS_ADMIN_API','CHESS_VARIATION_API','CHESS_GAME_API') and status <> 'VALID';
  expect_count(l_count,0,'Public and private maintenance objects are valid');
  select count(*) into l_count from user_tab_privs_made where grantee='ORAC_APX_PUB'
    and table_name in ('CHESS_GAMBIT_ECO_V','CHESS_VARIATION_ECO_V') and privilege='SELECT' and grantable='NO';
  expect_count(l_count,2,'Consumer has both read-only ECO views');
  select count(*) into l_count from user_tab_privs_made where grantee='ORAC_APX_PUB'
    and table_name in ('CHESS_GAMBIT_ECO','CHESS_VARIATION_ECO','CHESS_GAMBIT_ECO_V','CHESS_VARIATION_ECO_V')
    and privilege in ('INSERT','UPDATE','DELETE');
  expect_count(l_count,0,'Consumer has no direct ECO DML grant');
  select count(*) into l_count from user_constraints where constraint_name in ('CHS_OEC_ECO_FK','CHS_GAM_ECO_FK','CHS_GEC_ECO_FK','CHS_VEC_ECO_FK')
    and status='ENABLED' and validated='VALIDATED';
  expect_count(l_count,4,'Catalogue foreign keys are enabled and validated');
  orac_chess.chess_admin_api.save_opening_with_eco(l_opening,null,l_name,'OPENING',null,null,'C25:C29',l_opening_version);
  orac_chess.chess_admin_api.save_gambit_with_eco(l_gambit,null,l_name,null,'C25:C29',l_gambit_version);
  orac_chess.chess_variation_api.save_variation_with_eco(l_variation,null,l_opening,null,null,null,l_name,'MAIN',to_clob('1.e4 *'),null,null,'C29',l_variation_version);
  orac_chess.chess_admin_api.save_opening(l_opening,l_opening_version,l_name,'OPENING',null,null,l_new_version);
  l_opening_version := l_new_version;
  orac_chess.chess_admin_api.save_gambit(l_gambit,l_gambit_version,l_name,null,l_new_version);
  l_gambit_version := l_new_version;
  orac_chess.chess_variation_api.save_variation(l_variation,l_variation_version,l_opening,null,null,null,l_name,'MAIN',to_clob('1.e4 *'),null,null,l_new_version);
  l_variation_version := l_new_version;
  select count(*) into l_count from orac_chess.chess_opening_eco where opening_id=l_opening;
  expect_count(l_count,2,'Ordinary opening save preserves mappings');
  select count(*) into l_count from orac_chess.chess_gambit_eco where gambit_id=l_gambit;
  expect_count(l_count,2,'Ordinary gambit save preserves mappings');
  select count(*) into l_count from orac_chess.chess_variation_eco where variation_id=l_variation;
  expect_count(l_count,1,'Ordinary variation save preserves mappings');
  begin
    orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_opening_version-1,'changed','OPENING',null,null,'C29',l_new_version);
    raise_application_error(-20999,'Stale opening version was accepted');
  exception when others then if sqlcode != -20001 then raise; end if; end;
  begin
    orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_opening_version,l_name,'OPENING',null,l_opening,'C29',l_new_version);
    raise_application_error(-20999,'Opening cycle was accepted');
  exception when others then if sqlcode != -20004 then raise; end if; end;
  begin
    orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_opening_version,l_name,'OPENING',null,null,'Z99',l_new_version);
    raise_application_error(-20999,'Invalid opening ECO was accepted');
  exception when others then if sqlcode != -20014 then raise; end if; end;
  begin
    orac_chess.chess_variation_api.save_variation_with_eco(l_variation,l_variation_version-1,l_opening,null,null,null,l_name,'MAIN',to_clob('1.e4 *'),null,null,'C25',l_new_version);
    raise_application_error(-20999,'Stale variation version was accepted');
  exception when others then if sqlcode != -20001 then raise; end if; end;
  begin
    orac_chess.chess_variation_api.save_variation_with_eco(l_variation,l_variation_version,l_opening,null,null,null,l_name,'MAIN',to_clob('1.e5 *'),null,null,'C25',l_new_version);
    raise_application_error(-20999,'Invalid variation PGN was accepted');
  exception when others then if sqlcode != -20021 then raise; end if; end;
  begin
    orac_chess.chess_variation_api.save_variation_with_eco(l_variation,l_variation_version,l_opening,null,null,null,l_name,'MAIN',to_clob('1.e4 *'),null,null,'Z99',l_new_version);
    raise_application_error(-20999,'Invalid variation ECO was accepted');
  exception when others then if sqlcode != -20014 then raise; end if; end;
  select count(*) into l_count from chess_opening o join chess_opening_eco e on e.opening_id=o.opening_id
    where o.opening_id=l_opening and o.name=l_name and o.row_version=l_opening_version and e.eco_code in ('C25','C29');
  expect_count(l_count,2,'Rejected opening saves preserve values and mappings');
  select count(*) into l_count from chess_variation v join chess_variation_eco e on e.variation_id=v.variation_id
    where v.variation_id=l_variation and v.name=l_name and v.row_version=l_variation_version and e.eco_code='C29';
  expect_count(l_count,1,'Rejected variation saves preserve values and mappings');
  begin
    orac_chess.chess_admin_api.save_gambit_with_eco(l_gambit,l_gambit_version,null,null,'C29',l_new_version);
    raise_application_error(-20999,'Missing gambit name was accepted');
  exception when others then if sqlcode != -20015 then raise; end if; end;
  orac_chess.chess_game_api.save_game(l_game,null,'White','Black',null,null,null,'*',null,l_opening,to_clob('1.e4 *'),null,null,l_game_version);
  select count(*) into l_count from chess_game where game_id=l_game and eco_code is null and opening_id=l_opening;
  expect_count(l_count,1,'Game ECO is nullable and independent of opening');
  orac_chess.chess_game_api.save_game(l_game,l_game_version,'White','Black',null,null,null,'*','C29',l_opening,to_clob('1.e4 *'),null,null,l_new_version);
  l_game_version := l_new_version;
  select count(*) into l_count from chess_game where game_id=l_game and eco_code='C29';
  expect_count(l_count,1,'Game accepts a catalogue ECO code');
  select min(e.eco_code) into l_missing_code from chess_eco_code e
  where not exists (select 1 from chess_opening_eco x where x.eco_code=e.eco_code)
    and not exists (select 1 from chess_gambit_eco x where x.eco_code=e.eco_code)
    and not exists (select 1 from chess_variation_eco x where x.eco_code=e.eco_code)
    and not exists (select 1 from chess_game x where x.eco_code=e.eco_code);
  if l_missing_code is null then
    raise_application_error(-20999,'Missing-catalogue test requires one unused ECO code in the isolated fixture.');
  end if;
  savepoint chess_missing_eco;
  delete from chess_eco_code where eco_code=l_missing_code;
  begin
    orac_chess.chess_game_api.save_game(l_game,l_game_version,'White','Black',null,null,null,'*',l_missing_code,l_opening,to_clob('1.e4 *'),null,null,l_new_version);
    raise_application_error(-20999,'Missing catalogue game ECO was accepted');
  exception when others then if sqlcode != -20013 then raise; end if; end;
  rollback to chess_missing_eco;
  select count(*) into l_count from chess_game where game_id=l_game and eco_code='C29' and row_version=l_game_version;
  expect_count(l_count,1,'Rejected game ECO preserves code and version');
  begin
    orac_chess.chess_admin_api.save_gambit_with_eco(l_gambit,l_gambit_version,'should not persist',null,'C25:C25',l_new_version);
    raise_application_error(-20999,'Duplicate selection was accepted');
  exception when others then if sqlcode != -20009 then raise; end if; end;
  begin
    orac_chess.chess_admin_api.save_gambit_with_eco(l_gambit,l_gambit_version-1,'should not persist',null,'C29',l_new_version);
    raise_application_error(-20999,'Stale version was accepted');
  exception when others then if sqlcode != -20001 then raise; end if; end;
  select count(*) into l_count from orac_chess.chess_gambit where gambit_id=l_gambit and name=l_name and row_version=l_gambit_version;
  expect_count(l_count,1,'Rejected saves preserve subject and version');
  select count(*) into l_count from orac_chess.chess_gambit_eco where gambit_id=l_gambit;
  expect_count(l_count,2,'Rejected saves preserve assignments');
  begin
    orac_chess.chess_admin_api.save_gambit_with_eco(l_gambit,l_gambit_version,'should not persist',null,'Z99',l_new_version);
    raise_application_error(-20999,'Invalid selection was accepted');
  exception when others then if sqlcode != -20014 then raise; end if; end;
  begin
    insert into orac_chess.chess_gambit_eco (gambit_id,eco_code) values (l_gambit,'C25');
    raise_application_error(-20999,'Duplicate mapping was accepted');
  exception when others then if sqlcode != -1 then raise; end if; end;
  begin
    insert into orac_chess.chess_gambit_eco (gambit_id,eco_code) values (-999999999,'C25');
    raise_application_error(-20999,'Missing subject was accepted');
  exception when others then if sqlcode != -2291 then raise; end if; end;
  begin
    delete from orac_chess.chess_eco_code where eco_code='C25';
    raise_application_error(-20999,'Referenced catalogue code was deleted');
  exception when others then if sqlcode != -2292 then raise; end if; end;
  orac_chess.chess_admin_api.save_gambit_with_eco(l_gambit,l_gambit_version,l_name,null,null,l_new_version);
  select count(*) into l_count from orac_chess.chess_gambit_eco where gambit_id=l_gambit;
  expect_count(l_count,0,'Explicit empty selection clears');
  select count(*) into l_count from orac_chess.chess_opening_eco where opening_id=l_opening;
  expect_count(l_count,2,'Clear affects only its subject');
  orac_chess.chess_admin_api.save_opening_with_eco(l_opening,l_opening_version,l_name,'OPENING',null,null,null,l_new_version);
  select count(*) into l_count from orac_chess.chess_opening_eco where opening_id=l_opening;
  expect_count(l_count,0,'Explicit empty opening selection clears');
  orac_chess.chess_variation_api.save_variation_with_eco(l_variation,l_variation_version,l_opening,null,null,null,l_name,'MAIN',to_clob('1.e4 *'),null,null,null,l_new_version);
  select count(*) into l_count from orac_chess.chess_variation_eco where variation_id=l_variation;
  expect_count(l_count,0,'Explicit empty variation selection clears');
  rollback to eco_acceptance;
  dbms_output.put_line('ECO assignment checks passed; fixtures rolled back.');
exception when others then
  rollback to eco_acceptance;
  raise;
end;
/
