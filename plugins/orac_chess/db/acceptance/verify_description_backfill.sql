-- Author: Clive Bostock
-- Date: 10-Nov-2026
-- Purpose: Verify Vienna reset, missing video text, non-target and repeat semantics.
-- Usage: Run as ORAC_CHESS only in an authorised isolated installed catalogue.
-- Historical-stage check: run before chess_opening_v_strategy.sql in an isolated install.
-- The immutable description seed intentionally consumes the legacy six-column view.
-- All fixture writes are rolled back; this is not a production maintenance script.
whenever sqlerror exit failure rollback
set serveroutput on
variable opening_version number
variable video_version number
variable non_target number
savepoint description_acceptance;
declare
  l_opening orac_chess.chess_opening_v%rowtype;
  l_video orac_chess.chess_video_v%rowtype;
  l_id number;
  l_next number;
begin
  select opening_id,name,opening_type,description,parent_opening_id,row_version
  into l_opening from orac_chess.chess_opening_v where name='Vienna Game';
  orac_chess.chess_admin_api.save_opening_with_eco(l_opening.opening_id,l_opening.row_version,
    l_opening.name,l_opening.opening_type,to_clob('Vienna test description'),l_opening.parent_opening_id,'C25:C26',l_next);
  :opening_version := l_next + 1;
  select video_id,platform,external_video_id,video_url,title,creator,description,
    duration_seconds,published_on,created_on,updated_on,row_version
  into l_video from orac_chess.chess_video_v
  where platform='YouTube' and external_video_id='0ehLrDd2pn4';
  orac_chess.chess_admin_api.save_video(l_video.video_id,l_video.row_version,
    l_video.platform,l_video.external_video_id,l_video.video_url,l_video.title,l_video.creator,
    null,l_video.duration_seconds,l_video.published_on,l_next);
  :video_version := l_next + 1;
  orac_chess.chess_admin_api.save_opening(l_id,null,'Description acceptance non-target','OPENING',null,null,l_next);
  :non_target := l_id;
end;
/
@@../schema/seed_data/chess_descriptions_2026_11_10.sql
@@../schema/seed_data/chess_descriptions_2026_11_10.sql
declare
  l_description clob;
  l_version number;
  l_count number;
  l_id number;
  l_type varchar2(20);
  l_parent number;
  l_next number;
  l_video orac_chess.chess_video_v%rowtype;
begin
  select description,row_version,opening_id,opening_type,parent_opening_id
  into l_description,l_version,l_id,l_type,l_parent
  from orac_chess.chess_opening_v where name='Vienna Game';
  if dbms_lob.compare(l_description,to_clob('White develops Nc3 before Nf3, retaining the option of an early f-pawn advance.')) != 0
    or l_version != :opening_version
  then
    raise_application_error(-20001,'Whitespace/repeat opening backfill failed');
  end if;
  select description,row_version into l_description,l_version from orac_chess.chess_video_v
  where platform='YouTube' and external_video_id='0ehLrDd2pn4';
  if dbms_lob.compare(l_description,to_clob('ChessVibes instructional video presenting four levels of the interference tactic.')) != 0
    or l_version != :video_version
  then
    raise_application_error(-20001,'NULL/repeat video backfill failed');
  end if;
  select count(*) into l_count from orac_chess.chess_opening_v
  where opening_id=:non_target and description is null;
  if l_count != 1 then raise_application_error(-20001,'Non-target description changed'); end if;
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_id and eco_code='C25';
  if l_count != 1 then raise_application_error(-20001,'Canonical Vienna ECO missing'); end if;
  select count(*) into l_count from orac_chess.chess_opening_eco_v where opening_id=l_id and eco_code!='C25';
  if l_count != 0 then raise_application_error(-20001,'Vienna test ECO codes retained'); end if;
  orac_chess.chess_admin_api.save_opening(l_id,:opening_version,'Vienna Game',l_type,
    to_clob('Retain this maintained description'),l_parent,l_next);
  :opening_version := l_next + 1;
  select video_id,platform,external_video_id,video_url,title,creator,description,
    duration_seconds,published_on,created_on,updated_on,row_version
  into l_video from orac_chess.chess_video_v
  where platform='YouTube' and external_video_id='0ehLrDd2pn4';
  orac_chess.chess_admin_api.save_video(l_video.video_id,l_video.row_version,
    l_video.platform,l_video.external_video_id,l_video.video_url,l_video.title,l_video.creator,
    to_clob('Retain this maintained video description'),l_video.duration_seconds,l_video.published_on,l_next);
  :video_version := l_next;
end;
/
@@../schema/seed_data/chess_descriptions_2026_11_10.sql
declare
  l_description clob;
  l_version number;
begin
  select description,row_version into l_description,l_version
  from orac_chess.chess_opening_v where name='Vienna Game';
  if dbms_lob.compare(l_description,to_clob('White develops Nc3 before Nf3, retaining the option of an early f-pawn advance.')) != 0
    or l_version != :opening_version
  then
    raise_application_error(-20001,'Explicit Vienna reset failed');
  end if;
  select description,row_version into l_description,l_version from orac_chess.chess_video_v
  where platform='YouTube' and external_video_id='0ehLrDd2pn4';
  if dbms_lob.compare(l_description,to_clob('Retain this maintained video description')) != 0
    or l_version != :video_version
  then
    raise_application_error(-20001,'Maintained video description/version changed');
  end if;
  dbms_output.put_line('PASS: Vienna reset, NULL video, non-target and repeat preservation');
end;
/
rollback to description_acceptance;
