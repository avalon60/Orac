-- Author: Clive Bostock
-- Date: 25-Oct-2026
-- Purpose: Verify only the historical 161-changeset baseline through dictionary metadata.
-- Usage: Only for a separately approved historical baseline reconstruction in disposable FREEPDB1.
-- HISTORICAL BASELINE ONLY: excludes administration, grants, MLE and content source migrations.
-- Never use its baseline table/grant counts to validate the current full plugin release.
-- Current checks: verify_content_source_structure.sql, verify_admin_api.sql and runtime companions.
set serveroutput on
whenever sqlerror exit failure rollback

declare
  l_count number;
  l_default varchar2(32767);
  procedure assert_count(p_label varchar2, p_sql varchar2, p_expected number) is
  begin
    execute immediate p_sql into l_count;
    if l_count <> p_expected then
      raise_application_error(-20081, p_label || ': expected ' || p_expected || ', found ' || l_count);
    end if;
  end;
  procedure assert_key(p_name varchar2, p_type varchar2, p_table varchar2,
                       p_columns varchar2, p_reference varchar2 default null) is
    l_columns varchar2(4000);
    l_type varchar2(1);
    l_table varchar2(128);
    l_status varchar2(8);
    l_validated varchar2(13);
    l_reference varchar2(128);
    l_owner varchar2(128);
  begin
    select constraint_type, table_name, status, validated, r_constraint_name, r_owner
      into l_type, l_table, l_status, l_validated, l_reference, l_owner
    from dba_constraints where owner='ORAC_CHESS' and constraint_name=p_name;
    select listagg(column_name, ',') within group (order by position)
      into l_columns from dba_cons_columns
    where owner='ORAC_CHESS' and constraint_name=p_name;
    if l_type <> p_type or l_table <> p_table or l_status <> 'ENABLED'
      or l_validated <> 'VALIDATED' or nvl(l_columns, '-') <> p_columns
      or (p_reference is not null and
        (nvl(l_reference, '-') <> p_reference or nvl(l_owner, '-') <> 'ORAC_CHESS'))
    then
      raise_application_error(-20081, 'Constraint contract mismatch: ' || p_name);
    end if;
  end;

  procedure assert_check(p_name varchar2, p_table varchar2, p_condition varchar2) is
    l_condition varchar2(4000);
    function normalise(p_text varchar2) return varchar2 is
      l_result varchar2(4000);
      l_quoted boolean := false;
      l_char varchar2(1);
    begin
      -- Fold identifiers, preserving case and whitespace inside SQL literals.
      for i in 1 .. length(p_text) loop
        l_char := substr(p_text, i, 1);
        if l_char = chr(39) then
          l_quoted := not l_quoted;
          l_result := l_result || l_char;
        elsif l_quoted then
          l_result := l_result || l_char;
        elsif l_char <> '"' and not regexp_like(l_char, '[[:space:]]') then
          l_result := l_result || upper(l_char);
        end if;
      end loop;
      return l_result;
    end;
  begin
    select search_condition_vc into l_condition from dba_constraints
    where owner='ORAC_CHESS' and constraint_name=p_name and table_name=p_table
      and constraint_type='C' and status='ENABLED' and validated='VALIDATED';
    if normalise(l_condition) <> normalise(p_condition) or l_condition is null then
      raise_application_error(-20081, 'Check definition mismatch: ' || p_name);
    end if;
  end;

begin
  if sys_context('userenv','con_name') <> 'FREEPDB1' then
    raise_application_error(-20081, 'Verify the target PDB before inspecting ORAC_CHESS.');
  end if;
  assert_count('business tables', q'[select count(*) from dba_tables where owner='ORAC_CHESS' and table_name like 'CHESS_%']', 20);
  assert_count('primary keys', q'[select count(*) from dba_constraints where owner='ORAC_CHESS' and constraint_name like 'CHS_%' and constraint_type='P']', 20);
  assert_count('unique keys', q'[select count(*) from dba_constraints where owner='ORAC_CHESS' and constraint_name like 'CHS_%' and constraint_type='U']', 8);
  assert_count('check constraints', q'[select count(*) from dba_constraints where owner='ORAC_CHESS' and constraint_name like 'CHS_%' and constraint_type='C']', 13);
  assert_count('foreign keys', q'[select count(*) from dba_constraints where owner='ORAC_CHESS' and constraint_name like 'CHS_%' and constraint_type='R']', 31);
  assert_count('indexes', q'[select count(*) from dba_indexes where owner='ORAC_CHESS' and index_name like 'CHS_%']', 49);
  assert_count('PGN CLOB columns', q'[select count(*) from dba_tab_columns where owner='ORAC_CHESS' and ((table_name='CHESS_VARIATION' and column_name='PGN') or (table_name='CHESS_GAME' and column_name='PGN')) and data_type='CLOB']', 2);
  assert_count('image BLOB column', q'[select count(*) from dba_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_IMAGE' and column_name='IMAGE_CONTENT' and data_type='BLOB']', 1);
  assert_count('video audit timestamps', q'[select count(*) from dba_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_VIDEO' and column_name in ('CREATED_ON','UPDATED_ON') and data_type like 'TIMESTAMP%WITH TIME ZONE']', 2);
  assert_count('foreign schema references', q'[select count(*) from dba_constraints where owner='ORAC_CHESS' and constraint_type='R' and r_owner<>'ORAC_CHESS']', 0);
  assert_count('outgoing grants', q'[select count(*) from dba_tab_privs where owner='ORAC_CHESS' and grantee<>'ORAC_CHESS']', 0);
  assert_count('virtual ownership type', q'[select count(*) from dba_tab_cols where owner='ORAC_CHESS' and table_name='CHESS_VARIATION' and column_name='VARIATION_TYPE' and virtual_column='YES' and data_type='VARCHAR2' and char_length=1 and char_used='C']', 1);
  assert_count('obsolete opening ECO column', q'[select count(*) from dba_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_OPENING' and column_name='ECO_CODE']', 0);
  assert_count('obsolete name and ECO constraints', q'[select count(*) from dba_constraints where owner='ORAC_CHESS' and constraint_name in ('CHS_VAR_OPN_NAME_UK','CHS_VAR_GMB_NAME_UK','CHS_OPN_ECO_CK')]', 0);
  assert_count('obsolete name and ECO indexes', q'[select count(*) from dba_indexes where owner='ORAC_CHESS' and index_name in ('CHS_VAR_OPN_NAME_UX','CHS_VAR_GMB_NAME_UX','CHS_OPN_ECO_IX')]', 0);
  assert_count('subject name key columns', q'[select count(*) from dba_cons_columns where owner='ORAC_CHESS' and constraint_name='CHS_VAR_SUBJECT_NAME_UK' and ((position=1 and column_name='VARIATION_TYPE') or (position=2 and column_name='OPENING_ID') or (position=3 and column_name='GAMBIT_ID') or (position=4 and column_name='NAME'))]', 4);
  assert_count('subject name backing index', q'[select count(*) from dba_constraints where owner='ORAC_CHESS' and constraint_name='CHS_VAR_SUBJECT_NAME_UK' and index_name='CHS_VAR_SUBJECT_NAME_UX' and status='ENABLED' and validated='VALIDATED']', 1);
  assert_check('CHS_VAR_SUBJECT_CK', 'CHESS_VARIATION', q'~(opening_id is not null and gambit_id is null) or (opening_id is null and gambit_id is not null)~');
  assert_check('CHS_VAR_BRANCH_CK', 'CHESS_VARIATION', q'~(parent_variation_id is null and branch_ply is null and line_kind = 'MAIN') or (parent_variation_id is not null and branch_ply is not null and line_kind = 'ALTERNATIVE' and starting_fen is null)~');
  assert_check('CHS_VAR_PLY_CK', 'CHESS_VARIATION', q'~branch_ply is null or branch_ply >= 0~');
  assert_check('CHS_VAR_CYCLE_CK', 'CHESS_VARIATION', q'~parent_variation_id is null or parent_variation_id <> variation_id~');
  assert_check('CHS_OPN_PARENT_CK', 'CHESS_OPENING', q'~parent_opening_id is null or parent_opening_id <> opening_id~');
  assert_count('opening classification column', q'[select count(*) from dba_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_OPENING' and column_name='OPENING_TYPE' and data_type='VARCHAR2' and char_length=20 and char_used='C' and nullable='N' and default_on_null='NO']', 1);
  select data_default into l_default from dba_tab_columns
  where owner='ORAC_CHESS' and table_name='CHESS_OPENING' and column_name='OPENING_TYPE';
  if trim(l_default) <> '''OPENING''' or l_default is null then
    raise_application_error(-20081, 'Opening classification default mismatch');
  end if;
  assert_check('CHS_OPN_TYPE_CK', 'CHESS_OPENING', q'~opening_type in ('OPENING', 'SYSTEM')~');
  assert_check('CHS_OEC_ECO_CK', 'CHESS_OPENING_ECO', q'~regexp_like(eco_code, '^[A-E][0-9]{2}$')~');
  assert_key('CHS_VAR_SUBJECT_NAME_UK', 'U', 'CHESS_VARIATION', 'VARIATION_TYPE,OPENING_ID,GAMBIT_ID,NAME');
  assert_key('CHS_VAR_OPN_REF_UK', 'U', 'CHESS_VARIATION', 'VARIATION_ID,OPENING_ID');
  assert_key('CHS_VAR_GMB_REF_UK', 'U', 'CHESS_VARIATION', 'VARIATION_ID,GAMBIT_ID');
  assert_key('CHS_VAR_PARENT_OPN_FK', 'R', 'CHESS_VARIATION', 'PARENT_VARIATION_ID,OPENING_ID', 'CHS_VAR_OPN_REF_UK');
  assert_key('CHS_VAR_PARENT_GMB_FK', 'R', 'CHESS_VARIATION', 'PARENT_VARIATION_ID,GAMBIT_ID', 'CHS_VAR_GMB_REF_UK');
  assert_key('CHS_OEC_PK', 'P', 'CHESS_OPENING_ECO', 'OPENING_ID,ECO_CODE');
  assert_key('CHS_OEC_OPENING_FK', 'R', 'CHESS_OPENING_ECO', 'OPENING_ID', 'CHS_OPN_PK');
  dbms_output.put_line('ORAC_CHESS structure verified');
end;
/
