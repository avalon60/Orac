-- Author: Clive Bostock
-- Date: 10-Nov-2026
-- Purpose: Verify an authorised disposable Chess installation and two direct replays.
-- Usage: Run as ORAC_CHESS in an isolated database after a fresh managed install.
-- This script writes test edits, replays the batch, then rolls all test changes back.
whenever sqlerror exit failure rollback
set serveroutput on
variable opening_count number
variable gambit_count number
variable variation_count number
variable video_count number
variable edited_version number
savepoint starter_acceptance;
declare
  l_id number;
  l_version number;
  l_next number;
  l_type varchar2(20);
  l_parent number;
begin
  select count(*) into :opening_count from orac_chess.chess_opening_v;
  select count(*) into :gambit_count from orac_chess.chess_gambit_v;
  select count(*) into :variation_count from orac_chess.chess_variation_v;
  select count(*) into :video_count from orac_chess.chess_video_v;
  if :opening_count < 50 or :gambit_count < 40 or :variation_count < 190 or :video_count != 44
  then
    raise_application_error(-20001,'Fresh-install catalogue/video counts differ');
  end if;
  select opening_id,row_version,opening_type,parent_opening_id
  into l_id,l_version,l_type,l_parent from orac_chess.chess_opening_v where name='Colle System';
  orac_chess.chess_admin_api.save_opening(l_id,l_version,'Colle System',l_type,
    to_clob('Acceptance: retain this user description'),l_parent,l_next);
  :edited_version := l_next;
end;
/
@@../schema/seed_data/chess_batch_2026_11_10_starter_catalogue.sql
@@../schema/seed_data/chess_batch_2026_11_10_starter_catalogue.sql
declare
  l_count number;
  l_description clob;
  l_version number;
  l_history number;
begin
  select count(*) into l_count from orac_chess.chess_opening_v;
  if l_count != :opening_count then raise_application_error(-20001,'Opening replay duplicated rows'); end if;
  select count(*) into l_count from orac_chess.chess_gambit_v;
  if l_count != :gambit_count then raise_application_error(-20001,'Gambit replay duplicated rows'); end if;
  select count(*) into l_count from orac_chess.chess_variation_v;
  if l_count != :variation_count then raise_application_error(-20001,'Variation replay duplicated rows'); end if;
  select count(*) into l_count from orac_chess.chess_video_v;
  if l_count != :video_count then raise_application_error(-20001,'Video replay changed rows'); end if;
  select description,row_version into l_description,l_version from orac_chess.chess_opening_v where name='Colle System';
  if dbms_lob.compare(l_description,to_clob('Acceptance: retain this user description')) != 0 or l_version != :edited_version
  then
    raise_application_error(-20001,'Replay overwrote user edits');
  end if;
  select count(*) into l_history from databasechangelog
  where id='orac_chess_seed_2026_11_10_starter_catalogue' and author='clive';
  if l_history != 1 then raise_application_error(-20001,'Expected one once-only Liquibase history row'); end if;
  dbms_output.put_line('PASS: counts, 44 videos, two replays, edited field/version and once-only history');
end;
/
rollback to starter_acceptance;
