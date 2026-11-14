-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Purpose: Read-only evidence for the disabled Chess query release gate.
-- Usage: SQLcl using the CSV-mapped authorised inspection connection, then @plugins/orac_chess/db/acceptance/verify_query_reference.sql
-- Missing visibility is a failed gate; do not switch to an owner/admin alias.
whenever sqlerror exit failure rollback
set serveroutput on
set pagesize 100
set linesize 200
select sys_context('userenv','db_name') database_name,
       sys_context('userenv','session_user') session_user,
       sys_context('userenv','current_schema') current_schema,
       sys_context('userenv','con_name') container_name
from dual;

declare
  l_count number;
begin
  select count(*) into l_count from all_objects
   where owner='ORAC_CHESS' and object_type='VIEW' and status='VALID'
     and object_name in ('CHESS_QUERY_OPENING_V','CHESS_QUERY_OPENING_ALIAS_V',
       'CHESS_QUERY_GAMBIT_V','CHESS_QUERY_OPENING_GAMBIT_V','CHESS_QUERY_OPENING_ECO_V',
       'CHESS_QUERY_GAMBIT_ECO_V','CHESS_QUERY_VARIATION_ECO_V','CHESS_QUERY_ECO_CODE_V',
       'CHESS_QUERY_VARIATION_V','CHESS_QUERY_OPENING_TEXT_V','CHESS_QUERY_GAMBIT_TEXT_V',
       'CHESS_QUERY_VARIATION_LINE_V');
  if l_count<>12 then raise_application_error(-20890,'QUERY_PROJECTIONS_UNVERIFIED'); end if;
  select count(*) into l_count from all_tab_privs
   where table_schema='ORAC_CHESS' and grantee='ORAC_PLUGIN' and privilege='READ'
     and table_name in ('CHESS_QUERY_OPENING_V','CHESS_QUERY_OPENING_ALIAS_V',
       'CHESS_QUERY_GAMBIT_V','CHESS_QUERY_OPENING_GAMBIT_V','CHESS_QUERY_OPENING_ECO_V',
       'CHESS_QUERY_GAMBIT_ECO_V','CHESS_QUERY_VARIATION_ECO_V','CHESS_QUERY_ECO_CODE_V',
       'CHESS_QUERY_VARIATION_V','CHESS_QUERY_OPENING_TEXT_V','CHESS_QUERY_GAMBIT_TEXT_V',
       'CHESS_QUERY_VARIATION_LINE_V');
  if l_count<>12 then raise_application_error(-20891,'QUERY_GRANTS_UNVERIFIED'); end if;
  select count(*) into l_count from all_tab_columns
   where owner='ORAC_CHESS' and table_name like 'CHESS_QUERY_%'
     and (column_name in ('ANNOTATION','ROW_VERSION')
       or (column_name in ('PGN','STARTING_FEN') and table_name<>'CHESS_QUERY_VARIATION_LINE_V')
       or (column_name='DESCRIPTION' and table_name not in ('CHESS_QUERY_ECO_CODE_V', 'CHESS_QUERY_OPENING_TEXT_V','CHESS_QUERY_GAMBIT_TEXT_V')));
  if l_count<>0 then raise_application_error(-20892,'QUERY_EXCLUDED_COLUMN_VISIBLE'); end if;
  dbms_output.put_line('QUERY_PROJECTION_AND_READ_GRANT_COUNTS_VERIFIED_ONLY');
  dbms_output.put_line('ACTUAL_CONTENT_PROVENANCE_CLASSIFICATION_AND_EFFECTIVE_PRIVILEGE_REVIEW_STILL_REQUIRED');
end;
/

select owner,name,referenced_owner,referenced_name,referenced_type,referenced_link_name
from all_dependencies
where owner='ORAC_CHESS' and name like 'CHESS_QUERY_%'
order by name,referenced_name;
select table_schema,table_name,privilege,grantable
from all_tab_privs where grantee='ORAC_PLUGIN'
order by table_schema,table_name,privilege;
select privilege from session_privs order by privilege;
select opening_type,count(*) row_count from orac_chess.chess_query_opening_v group by opening_type;
select variation_type,count(*) row_count from orac_chess.chess_query_variation_v group by variation_type;
select count(*) upstream_eco_rows from orac_chess.chess_query_eco_code_v;
