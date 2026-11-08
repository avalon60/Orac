-- Author: Clive Bostock
-- Date: 02-Nov-2026
-- Purpose: Parse installed APEX queries/processes without executing protected workflows.
-- Usage: sql -name orac-db @plugins/orac_chess/db/acceptance/verify_apex_sources.sql
-- SELECT sources are parsed. PL/SQL is executed inside IF FALSE to force bind
-- compilation while preventing all original workflow statements from running.
-- This remains a source check, not authenticated browser smoke.
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on
set define off
declare
  l_app number;
  l_cursor integer;
  l_source clob;
  l_count number := 0;
  procedure parse_source(p_source clob,p_name varchar2,p_plsql boolean default false) is
    l_text clob;
    l_bind_scan clob;
    l_bind varchar2(128);
    l_index pls_integer := 1;
    l_result integer;
    type bound_set is table of boolean index by varchar2(128);
    l_bound bound_set;
    l_null varchar2(32767);
  begin
    l_cursor:=dbms_sql.open_cursor;
    if p_plsql then
      -- Only the wrapper runs. The original block is never entered, even when
      -- its own request conditions would otherwise permit a mutation.
      l_text:='begin if false then '||p_source||' end if; end;';
    else
      l_text:=p_source;
    end if;
    dbms_sql.parse(l_cursor,l_text,dbms_sql.native);
    if p_plsql then
      -- APEX session-state binds are VARCHAR2 at this boundary. Strip quoted
      -- literals so URL/string colons are not mistaken for actual bind names.
      l_bind_scan:=regexp_replace(p_source,q'~'([^']|'')*'~','');
      loop
        l_bind:=regexp_substr(l_bind_scan,':[A-Za-z][A-Za-z0-9_]*',1,l_index);
        exit when l_bind is null;
        if not l_bound.exists(upper(l_bind)) then
          dbms_sql.bind_variable(l_cursor,l_bind,l_null);
          l_bound(upper(l_bind)):=true;
        end if;
        l_index:=l_index+1;
      end loop;
      l_result:=dbms_sql.execute(l_cursor);
    end if;
    dbms_sql.close_cursor(l_cursor);
    l_count:=l_count+1;
  exception when others then
    if dbms_sql.is_open(l_cursor) then dbms_sql.close_cursor(l_cursor); end if;
    raise_application_error(-20997,p_name||': '||sqlerrm);
  end;

begin
  if user!='SYSTEM' or sys_context('userenv','con_name')!='FREEPDB1' then raise_application_error(-20998,'Wrong source-verification target'); end if;
  select application_id into l_app from apex_applications where alias='ORAC_CHESS_ADMIN' and workspace='ORAC' and owner='ORAC_APX_PUB';
  for r in (select page_id,region_name,region_source from apex_application_page_regions where application_id=l_app and region_source is not null)
  loop
    if regexp_like(ltrim(r.region_source),'^select[[:space:]]','i') then
      parse_source(r.region_source,'Region '||r.page_id||'/'||r.region_name);
    elsif regexp_like(ltrim(r.region_source),'^(declare|begin)[[:space:]]','i') then
      l_source:='declare function render_region return clob is begin '||r.region_source||' end; begin null; end;';
      parse_source(l_source,'Dynamic region '||r.page_id||'/'||r.region_name,true);
    end if;
  end loop;
  for r in (select page_id,process_name,process_source from apex_application_page_proc where application_id=l_app and process_source is not null)
  loop
    if regexp_like(ltrim(r.process_source),'^(declare|begin)[[:space:]]','i') then
      parse_source(r.process_source,'Process '||r.page_id||'/'||r.process_name,true);
    end if;
  end loop;
  dbms_output.put_line('CHESS_APEX_SOURCE_PARSE_PASSED count='||l_count||' app='||l_app);
end;
/
exit
