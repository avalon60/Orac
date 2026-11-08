--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Provide the complete ECO code reference.
-- Purpose: Supply installation-owned reference descriptions.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_ECO_PK'
alter table orac_chess.chess_eco_code add constraint chs_eco_pk primary key (eco_code) using index orac_chess.chs_eco_code_ux;
--rollback alter table orac_chess.chess_eco_code drop constraint chs_eco_pk keep index;
