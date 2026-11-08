-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Rollback acceptance of subject video API transactions and versions.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.
-- Purpose: Verify atomic subject video operations, stale protection and caller-owned transactions.
-- Usage: Approved DEV sql -name orac_apx_pub @plugins/orac_chess/db/acceptance/verify_subject_videos.sql
-- Also included by verify_admin_api.sql; all fixtures are rolled back.
whenever sqlerror exit sql.sqlcode rollback
set define off
set serveroutput on
declare
  l_id number;
  l_subject_version number;
  l_video number;
  l_video_version number;
  l_failed_video number;
  l_new_subject number;
  l_new_video number;
  l_count number;
  l_actual number;
  l_kind varchar2(7);
  l_prefix varchar2(100) := '__SUBJECT_VIDEO_'||sys_context('userenv','sessionid');
  procedure check_true(p_ok boolean,p_message varchar2) is
  begin
    if p_ok is null or not p_ok then raise_application_error(-20999,p_message); end if;
  end check_true;
  procedure expect_error(p_actual number,p_expected number) is
  begin
    check_true(p_actual=p_expected,'Unexpected error: '||p_actual||'; expected '||p_expected);
  end expect_error;
  procedure create_linked(p_kind varchar2,p_id number,p_expected number,p_external varchar2) is
  begin
    orac_chess.chess_admin_api.create_video_for_subject('Other',p_external,'https://example.com/'||p_external,p_external,null,null,65,date '2026-11-08',p_kind,p_id,p_expected,l_failed_video,l_new_subject,l_new_video);
  end create_linked;
begin
  if user not in ('ORAC_APX_PUB','SYSTEM') or sys_context('userenv','con_name')!='FREEPDB1' then
    raise_application_error(-20998,'This harness requires the approved DEV target and principal.');
  end if;
  savepoint subject_video_caller;
  for i in 1..2 loop
    l_id := null;
    l_kind := case i when 1 then 'OPENING' else 'GAMBIT' end;
    if i=1 then
      orac_chess.chess_admin_api.save_opening(l_id,null,l_prefix||i,'OPENING',null,null,l_subject_version);
    else
      orac_chess.chess_admin_api.save_gambit(l_id,null,l_prefix||i,null,l_subject_version);
    end if;
    create_linked(l_kind,l_id,l_subject_version,l_prefix||i);
    l_video := l_failed_video;
    l_video_version := l_new_video;
    l_subject_version := l_new_subject;
    check_true(l_subject_version=2 and l_video_version=2,'Creation increments subject once and video once for its link');
    if i=1 then
      select count(*) into l_count from orac_chess.chess_video_opening_v where opening_id=l_id and video_id=l_video;
    else
      select count(*) into l_count from orac_chess.chess_video_gambit_v where gambit_id=l_id and video_id=l_video;
    end if;
    check_true(l_count=1,'Created video and subject link agree');
    -- Failures after save_video must remove the inserted video and preserve caller fixtures.
    begin create_linked(l_kind,l_id,1,l_prefix||i||'_stale'); raise_application_error(-20999,'Stale subject accepted');
    exception when others then expect_error(sqlcode,-20001); end;
    begin create_linked(l_kind,-1,1,l_prefix||i||'_missing'); raise_application_error(-20999,'Missing subject accepted');
    exception when others then expect_error(sqlcode,-20008); end;
    begin create_linked('INVALID',l_id,l_subject_version,l_prefix||i||'_invalid'); raise_application_error(-20999,'Invalid subject kind accepted');
    exception when others then expect_error(sqlcode,-20014); end;
    begin create_linked(l_kind,l_id,l_subject_version,l_prefix||i); raise_application_error(-20999,'Duplicate video accepted');
    exception when others then expect_error(sqlcode,-20009); end;
    select count(*) into l_count from orac_chess.chess_video_v where external_video_id like l_prefix||i||'%';
    check_true(l_count=1,'Failed create-and-link leaves no orphan video and retains caller video');
    begin
      orac_chess.chess_admin_api.set_subject_video_link(l_kind,l_id,l_subject_version,l_video,l_video_version,true,l_new_subject,l_new_video);
      raise_application_error(-20999,'Duplicate link accepted');
    exception when others then expect_error(sqlcode,-20009); end;
    begin
      orac_chess.chess_admin_api.set_subject_video_link(l_kind,l_id,l_subject_version-1,l_video,l_video_version,false,l_new_subject,l_new_video);
      raise_application_error(-20999,'Stale subject link accepted');
    exception when others then expect_error(sqlcode,-20001); end;
    begin
      orac_chess.chess_admin_api.set_subject_video_link(l_kind,l_id,l_subject_version,l_video,l_video_version-1,false,l_new_subject,l_new_video);
      raise_application_error(-20999,'Stale video link accepted');
    exception when others then expect_error(sqlcode,-20001); end;
    begin
      orac_chess.chess_admin_api.set_subject_video_link(l_kind,l_id,l_subject_version,-1,1,false,l_new_subject,l_new_video);
      raise_application_error(-20999,'Missing video accepted');
    exception when others then expect_error(sqlcode,-20008); end;
    orac_chess.chess_admin_api.set_subject_video_link(l_kind,l_id,l_subject_version,l_video,l_video_version,false,l_new_subject,l_new_video);
    l_subject_version := l_new_subject;
    l_video_version := l_new_video;
    check_true(l_subject_version=3 and l_video_version=3,'Unlink increments each aggregate exactly once');
    select count(*) into l_count from orac_chess.chess_video_v where video_id=l_video;
    check_true(l_count=1,'Unlink retains shared video');
    begin
      orac_chess.chess_admin_api.set_subject_video_link(l_kind,l_id,l_subject_version,l_video,l_video_version,false,l_new_subject,l_new_video);
      raise_application_error(-20999,'Missing link accepted');
    exception when others then expect_error(sqlcode,-20012); end;
    orac_chess.chess_admin_api.set_subject_video_link(l_kind,l_id,l_subject_version,l_video,l_video_version,true,l_new_subject,l_new_video);
    check_true(l_new_subject=4 and l_new_video=4,'Failed mutations do not increment either version');
    -- Metadata-only edits increment the video while leaving its subject token alone.
    orac_chess.chess_admin_api.save_video(l_video,l_new_video,'Other',l_prefix||i,'https://example.com/'||l_prefix||i,'Changed title',null,null,65,date '2026-11-08',l_video_version);
    if i=1 then
      select row_version into l_actual from orac_chess.chess_opening_v where opening_id=l_id;
    else
      select row_version into l_actual from orac_chess.chess_gambit_v where gambit_id=l_id;
    end if;
    check_true(l_actual=l_new_subject and l_video_version=5,'Metadata edits leave subject version unchanged');
  end loop;
  -- A commit inside any API invalidates this caller savepoint and fails acceptance.
  rollback to subject_video_caller;
  select count(*) into l_count from orac_chess.chess_video_v where external_video_id like l_prefix||'%';
  check_true(l_count=0,'Caller rollback removes all created videos');
  dbms_output.put_line('CHESS_SUBJECT_VIDEO_ACCEPTANCE_PASSED');
exception
  when others then rollback; raise;
end;
/
