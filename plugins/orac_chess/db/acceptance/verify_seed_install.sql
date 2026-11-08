-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Purpose: Verify an isolated fresh managed install exposes the bootstrap through consumer views.
-- Usage: Approved isolated ORAC_CHESS owner SQLcl session: @verify_seed_install.sql
-- Read-only. This acceptance is deliberately exact and requires an otherwise empty catalogue.
whenever sqlerror exit failure rollback
set serveroutput on
set define off
declare
  l_count number;
  procedure expect(p_actual number,p_expected number,p_message varchar2) is
  begin
    if p_actual <> p_expected
    then
      raise_application_error(-20999,p_message || ': got ' || p_actual || ', expected ' || p_expected);
    end if;
  end;
begin
  select count(*) into l_count from orac_chess.chess_video_v;
  expect(l_count,44,'Fresh consumer video count');
  select count(*) into l_count from orac_chess.chess_content_source_v;
  expect(l_count,8,'Fresh source count including five initial sources');
  select count(*) into l_count from orac_chess.chess_content_source_v
  where creator in ('Yellow Rook','ChessTeacher Games','The Chess Giant') and author is null and notes is null;
  expect(l_count,3,'New sources have blank author and notes');
  select count(*) into l_count from orac_chess.chess_video_v where published_on is not null;
  expect(l_count,0,'Blank publication dates stay unknown');
  select count(*) into l_count from orac_chess.chess_video_v where description is not null and dbms_lob.getlength(description) > 0;
  expect(l_count,2,'The two descriptions remain prose');
  select count(*) into l_count from orac_chess.chess_video_opening_v;
  expect(l_count,0,'No opening links inferred from prose');
  select count(*) into l_count from orac_chess.chess_video_gambit_v;
  expect(l_count,0,'No gambit links inferred from prose');
  select count(*) into l_count from databasechangelog
  where id = 'orac_chess_seed_2026_11_07_bootstrap' and author = 'clive' and exectype = 'EXECUTED';
  expect(l_count,1,'Bootstrap history is recorded exactly once');
  dbms_output.put_line('PASS: fresh managed bootstrap and consumer projections');
end;
/
