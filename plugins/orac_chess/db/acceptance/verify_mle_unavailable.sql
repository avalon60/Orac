-- Author: Clive Bostock
-- Date: 06-Nov-2026
-- Purpose: Prove public PGN writes fail closed with MLE disabled for this session.
-- Usage: Approved consumer SQLcl @plugins/orac_chess/db/acceptance/verify_mle_unavailable.sql
-- Requires ALTER SESSION for the session-modifiable MLE_PROG_LANGUAGES parameter.
-- An unsupported parameter/permission fails this test; no global setting is changed.
whenever sqlerror exit failure rollback
whenever oserror exit failure rollback
set define off
set serveroutput on
declare
  l_id number;
  l_version number;
  l_count number;
  l_before number;
begin
  if user<>'ORAC_APX_PUB' or sys_context('userenv','con_name')<>'FREEPDB1' then
    raise_application_error(-20998,'Requires approved DEV consumer session');
  end if;
  select count(*) into l_before from orac_chess.chess_game_v;
  execute immediate 'alter session set mle_prog_languages=OFF';
  begin
    orac_chess.chess_game_api.save_game(l_id,null,'Unavailable probe','Black',null,null,null,'*',null,null,to_clob('1.e4 *'),null,null,l_version);
    raise_application_error(-20999,'Unavailable runtime accepted a write');
  exception when others then
    if sqlcode<>-20020 then raise; end if;
  end;
  select count(*) into l_count from orac_chess.chess_game_v;
  if l_count<>l_before then raise_application_error(-20999,'Unavailable runtime mutated games'); end if;
  rollback;
  dbms_output.put_line('CHESS_MLE_UNAVAILABLE_FAIL_CLOSED_PASSED');
end;
/
-- SQLcl exits immediately; the session-only setting is discarded, including on failure.
exit
