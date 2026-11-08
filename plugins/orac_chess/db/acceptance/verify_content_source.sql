-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Purpose: Verify content source behaviour through approved consumer APIs and roll back fixtures.
-- Usage: sql -name orac_apx_pub @plugins/orac_chess/db/acceptance/verify_content_source.sql
-- Requires approved DEV deployment and consumer connection; no DDL or commit is performed.
whenever sqlerror exit sql.sqlcode rollback
set define off
set serveroutput on

declare
  l_prefix varchar2(100) := '__SOURCE_ACCEPTANCE_' || sys_context('userenv','sessionid');
  l_version number;
  l_old number;
  l_other_version number;
  l_video1 number;
  l_video2 number;
  l_video_version1 number;
  l_video_version2 number;
  l_count number;
  l_checks number := 0;
  l_notes clob := to_clob(rpad('A',30000,'A')) || rpad('B',30000,'B');
  procedure assert_true(p_ok boolean, p_message varchar2) is
  begin
    if p_ok is null or not p_ok then
      raise_application_error(-20999,p_message);
    end if;
    l_checks := l_checks + 1;
  end;
  procedure expected(p_code number, p_actual number, p_message varchar2) is
  begin
    assert_true(p_code=p_actual,p_message||': expected '||p_code||', received '||p_actual);
  end;
begin
  if user != 'ORAC_APX_PUB' or sys_context('userenv','con_name') != 'FREEPDB1' then
    raise_application_error(-20998,'Requires the verified DEV consumer connection.');
  end if;
  savepoint content_source_acceptance;
  orac_chess.chess_admin_api.save_content_source(null,null,l_prefix,'Author',l_notes,l_version);
  assert_true(l_version=1,'Insert initializes source version');
  select dbms_lob.getlength(notes) into l_count from orac_chess.chess_content_source_v where creator=l_prefix;
  assert_true(l_count=60000,'Long editable notes survive the public API');
  begin
    orac_chess.chess_admin_api.save_content_source(null,null,l_prefix,'Duplicate',null,l_other_version);
    raise_application_error(-20999,'Duplicate creator accepted');
  exception when others then expected(-20009,sqlcode,'Natural key rejects duplicate creator'); end;
  begin
    orac_chess.chess_admin_api.save_content_source(null,null,'   ',null,null,l_other_version);
    raise_application_error(-20999,'Blank creator accepted');
  exception when others then expected(-20015,sqlcode,'Blank creator rejected'); end;
  l_old := l_version;
  orac_chess.chess_admin_api.save_content_source(l_prefix,l_version,l_prefix,null,'Edited notes',l_version);
  assert_true(l_version=l_old+1,'Update advances version');
  begin
    orac_chess.chess_admin_api.save_content_source(l_prefix,l_old,l_prefix,'Stale',null,l_other_version);
    raise_application_error(-20999,'Stale update accepted');
  exception when others then expected(-20001,sqlcode,'Stale source update rejected'); end;
  begin
    orac_chess.chess_admin_api.delete_content_source(l_prefix,l_old);
    raise_application_error(-20999,'Stale delete accepted');
  exception when others then expected(-20001,sqlcode,'Stale source delete rejected'); end;
  orac_chess.chess_admin_api.save_video(l_video1,null,'WEB',l_prefix||'_1','https://example.com/1','First',l_prefix,null,null,null,l_video_version1);
  orac_chess.chess_admin_api.save_video(l_video2,null,'WEB',l_prefix||'_2','https://example.com/2','Second',l_prefix,null,null,null,l_video_version2);
  select count(*) into l_count from orac_chess.chess_video_v where creator=l_prefix;
  assert_true(l_count=2,'Two independent videos may use one creator');
  begin
    orac_chess.chess_admin_api.save_content_source(l_prefix,l_version,l_prefix||'_renamed',null,null,l_other_version);
    raise_application_error(-20999,'Referenced rename accepted');
  exception when others then expected(-20010,sqlcode,'Referenced source rename rejected'); end;
  begin
    orac_chess.chess_admin_api.delete_content_source(l_prefix,l_version);
    raise_application_error(-20999,'Referenced delete accepted');
  exception when others then expected(-20010,sqlcode,'Referenced source delete rejected'); end;
  select count(*) into l_count from orac_chess.chess_video_v
  where creator=l_prefix and ((video_id=l_video1 and row_version=l_video_version1)
    or (video_id=l_video2 and row_version=l_video_version2));
  assert_true(l_count=2,'Rejected source operations preserve videos and versions');
  begin
    orac_chess.chess_admin_api.save_video(l_video1,l_video_version1,'WEB',l_prefix||'_1','https://example.com/1','First',l_prefix||'_unknown',null,null,null,l_other_version);
    raise_application_error(-20999,'Unknown creator accepted');
  exception when others then expected(-20013,sqlcode,'Unknown video creator rejected'); end;
  select count(*) into l_count from orac_chess.chess_video_v where video_id=l_video1 and creator=l_prefix and row_version=l_video_version1;
  assert_true(l_count=1,'Failed video save rolls back its changes only');
  orac_chess.chess_admin_api.save_video(l_video1,l_video_version1,'WEB',l_prefix||'_1','https://example.com/1','First',null,null,null,null,l_other_version);
  l_video_version1 := l_other_version;
  select count(*) into l_count from orac_chess.chess_video_v where video_id=l_video1 and creator is null;
  assert_true(l_count=1,'Video creator remains optional');
  orac_chess.chess_admin_api.delete_video(l_video1,l_video_version1);
  orac_chess.chess_admin_api.delete_video(l_video2,l_video_version2);
  orac_chess.chess_admin_api.save_content_source(l_prefix,l_version,l_prefix||'_renamed',null,l_notes,l_other_version);
  assert_true(l_other_version=l_version+1,'Unreferenced creator can be renamed');
  l_version := l_other_version;
  begin
    execute immediate 'insert into orac_chess.chess_content_source (creator) values (:1)' using l_prefix||'_bypass';
    raise_application_error(-20999,'Direct source DML accepted');
  exception when others then assert_true(sqlcode in (-942,-1031),'Direct source DML denied'); end;
  begin
    execute immediate 'begin orac_chess.chess_admin_tapi.delete_content_source(:1,:2); end;' using l_prefix||'_renamed',l_version;
    raise_application_error(-20999,'Private TAPI accepted');
  exception when others then assert_true(sqlcode in (-6550,-1031),'Private TAPI denied'); end;
  orac_chess.chess_admin_api.delete_content_source(l_prefix||'_renamed',l_version);
  select count(*) into l_count from orac_chess.chess_content_source_v where creator like l_prefix||'%';
  assert_true(l_count=0,'Unreferenced CRUD removes only its source');
  rollback to content_source_acceptance;
  dbms_output.put_line('Content source acceptance passed: '||l_checks||' checks; fixtures rolled back.');
exception when others then
  rollback;
  raise;
end;
/
