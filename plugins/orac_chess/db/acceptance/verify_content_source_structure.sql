-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Purpose: Verify deployed content source keys, nullable video relationship and least privileges.
-- Usage: In an approved DEV admin session run @plugins/orac_chess/db/acceptance/verify_content_source_structure.sql
whenever sqlerror exit sql.sqlcode rollback
set serveroutput on

declare
  l_count number;
  procedure assert_count(p_sql varchar2, p_expected number, p_label varchar2) is
  begin
    execute immediate p_sql into l_count;
    if l_count != p_expected then
      raise_application_error(-20999,p_label||': expected '||p_expected||', found '||l_count);
    end if;
  end;
begin
  if sys_context('userenv','con_name') != 'FREEPDB1' then
    raise_application_error(-20998,'Requires the verified DEV PDB.');
  end if;
  assert_count(q'[select count(*) from dba_constraints c join dba_cons_columns k on k.owner=c.owner and k.constraint_name=c.constraint_name where c.owner='ORAC_CHESS' and c.table_name='CHESS_CONTENT_SOURCE' and c.constraint_name='CHS_CSR_PK' and c.constraint_type='P' and c.status='ENABLED' and c.validated='VALIDATED' and c.index_name='CHS_CSR_CREATOR_UX' and k.column_name='CREATOR' and k.position=1]',1,'Creator natural primary key and supporting index');
  assert_count(q'[select count(*) from dba_constraints where owner='ORAC_CHESS' and table_name='CHESS_CONTENT_SOURCE' and constraint_type in ('P','U')]',1,'No surrogate or redundant unique key');
  assert_count(q'[select count(*) from dba_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_CONTENT_SOURCE' and column_name='CREATOR' and data_type='VARCHAR2' and char_used='C' and char_length=300 and nullable='N']',1,'Creator column contract');
  assert_count(q'[select count(*) from dba_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_CONTENT_SOURCE' and column_name='NOTES' and data_type='CLOB']',1,'Editable notes CLOB');
  assert_count(q'[select count(*) from dba_constraints c join dba_cons_columns k on k.owner=c.owner and k.constraint_name=c.constraint_name where c.owner='ORAC_CHESS' and c.table_name='CHESS_VIDEO' and c.constraint_name='CHS_VID_CREATOR_FK' and c.constraint_type='R' and c.r_owner='ORAC_CHESS' and c.r_constraint_name='CHS_CSR_PK' and c.delete_rule='NO ACTION' and c.status='ENABLED' and c.validated='VALIDATED' and k.column_name='CREATOR' and k.position=1]',1,'Restrictive creator foreign key');
  assert_count(q'[select count(*) from dba_tab_columns where owner='ORAC_CHESS' and table_name='CHESS_VIDEO' and column_name='CREATOR' and nullable='Y']',1,'Video creator remains nullable');
  assert_count(q'[select count(*) from dba_indexes i join dba_ind_columns k on k.index_owner=i.owner and k.index_name=i.index_name where i.owner='ORAC_CHESS' and i.index_name='CHS_VID_CREATOR_IX' and i.uniqueness='NONUNIQUE' and k.column_name='CREATOR' and k.column_position=1]',1,'Nonunique video creator index');
  assert_count(q'[select count(*) from dba_tab_privs where owner='ORAC_CHESS' and table_name='CHESS_CONTENT_SOURCE_V' and grantee='ORAC_APX_PUB' and privilege='SELECT']',1,'Approved consumer read view');
  assert_count(q'[select count(*) from dba_tab_privs where owner='ORAC_CHESS' and table_name in ('CHESS_CONTENT_SOURCE','CHESS_ADMIN_TAPI') and grantee in ('ORAC_APX_PUB','PUBLIC','ORAC_PLUGIN')]',0,'No direct table or private TAPI grant');
  assert_count(q'[select count(*) from orac_chess.chess_video v where v.creator is not null and not exists (select 1 from orac_chess.chess_content_source s where s.creator=v.creator)]',0,'Existing video creators migrated');
  dbms_output.put_line('Content source structure passed.');
end;
/
