-- Author: Clive Bostock
-- Date: 14-Nov-2026
-- Purpose: Execute installed read-only PGN callbacks against existing DEV catalogue data.
-- Usage: sql -name orac-db @plugins/orac_chess/db/acceptance/verify_pgn_viewer.sql
-- No catalogue fixtures, writes, schema objects or APEX sessions are created.
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on
set define off
declare
  l_source clob;
  l_original clob;
  l_output clob;
  l_id number;
  l_owner number;
  l_other number;
  l_cursor integer;
  l_result integer;
  procedure require(p_ok boolean,p_message varchar2) is
  begin
    if p_ok is null or not p_ok then raise_application_error(-20990,p_message); end if;
  end;
  function request(p_action varchar2,p_id varchar2,p_owner number) return clob is
    l_json clob;
  begin
    apex_application.g_x01:=p_action;
    apex_application.g_x02:=p_id;
    apex_application.g_x03:='0';
    apex_json.initialize_clob_output;
    l_cursor:=dbms_sql.open_cursor;
    dbms_sql.parse(l_cursor,l_source,dbms_sql.native);
    dbms_sql.bind_variable(l_cursor,':P11_OPENING_ID',to_char(p_owner));
    l_result:=dbms_sql.execute(l_cursor);
    dbms_sql.close_cursor(l_cursor);
    l_json:=apex_json.get_clob_output;
    -- Copy before free_output releases its temporary CLOB.
    dbms_lob.createtemporary(l_output,true);
    dbms_lob.append(l_output,l_json);
    apex_json.free_output;
    return l_output;
  end;
begin
  require(user='SYSTEM' and sys_context('userenv','con_name')='FREEPDB1','Wrong DEV target');
  select process_source into l_source from apex_application_page_proc
    where application_id=10030 and page_id=11 and process_name='PGN_VIEWER';
  select variation_id,opening_id,pgn into l_id,l_owner,l_original from orac_chess.chess_variation_v
    where opening_id is not null and parent_variation_id is null and pgn is not null fetch first 1 row only;
  l_output:=request('LINE',to_char(l_id),l_owner);
  require(json_value(l_output,'$.id' returning number)=l_id,'Selected line identity mismatch');
  require(dbms_lob.compare(l_original,to_clob(json_value(l_output,'$.pgn' returning varchar2(4000))))=0,'Selected PGN was altered or truncated');
  dbms_lob.freetemporary(l_output);
  l_output:=request('LIST',null,l_owner);
  require(json_exists(l_output,'$.lines[0]'),'Metadata list missing');
  require(not json_exists(l_output,'$.lines[0].pgn'),'Metadata fetched PGN CLOBs');
  dbms_lob.freetemporary(l_output);
  select opening_id into l_other from orac_chess.chess_opening_v where opening_id<>l_owner fetch first 1 row only;
  l_output:=request('LINE',to_char(l_id),l_other);
  require(json_value(l_output,'$.error') is not null,'Unrelated subject was not rejected');
  dbms_lob.freetemporary(l_output);
  l_output:=request('LINE','invalid',l_owner);
  require(json_value(l_output,'$.error') is not null,'Invalid numeric identity was not rejected');
  dbms_lob.freetemporary(l_output);
  dbms_output.put_line('CHESS_PGN_VIEWER_CALLBACKS_PASSED app=10030');
end;
/
exit
