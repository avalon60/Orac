--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Provide the complete ECO code reference.
-- Purpose: Supply installation-owned reference descriptions.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_check context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_ECO_CODE_CK'
alter table orac_chess.chess_eco_code add constraint chs_eco_code_ck check (regexp_like(eco_code, '^[A-E][0-9]{2}$', 'c'));
--rollback alter table orac_chess.chess_eco_code drop constraint chs_eco_code_ck;
