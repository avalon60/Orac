--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_preflight context:plugin,prod labels:plugin stripComments:false endDelimiter:/
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:5 select count(*) from all_tab_columns where owner='ORAC_CHESS' and ((table_name='CHESS_ECO_CODE' and column_name='ECO_CODE' and data_type='VARCHAR2' and char_length=3 and nullable='N') or (table_name='CHESS_ECO_CODE' and column_name='DESCRIPTION' and data_type='CLOB' and nullable='N') or (table_name='CHESS_OPENING_ECO' and column_name='ECO_CODE' and data_type='VARCHAR2' and char_length=3 and nullable='N') or (table_name='CHESS_OPENING_ECO' and column_name='OPENING_ID' and data_type='NUMBER' and nullable='N') or (table_name='CHESS_GAME' and column_name='ECO_CODE' and data_type='VARCHAR2' and char_length=3 and nullable='Y'))
--precondition-sql-check expectedResult:500 select count(*) from orac_chess.chess_eco_code
--precondition-sql-check expectedResult:500 select count(*) from orac_chess.chess_eco_code where regexp_like(eco_code, '^[A-E][0-9]{2}$', 'c') and description is not null and dbms_lob.getlength(description)>0
--precondition-sql-check expectedResult:0 select count(*) from orac_chess.chess_opening_eco o where not exists (select 1 from orac_chess.chess_eco_code e where e.eco_code=o.eco_code)
--precondition-sql-check expectedResult:0 select count(*) from orac_chess.chess_game g where g.eco_code is not null and not exists (select 1 from orac_chess.chess_eco_code e where e.eco_code=g.eco_code)
begin
  null; -- Preconditions deliberately halt; investigate incompatible installations before retrying.
end;
/
--rollback select 1 from dual;
