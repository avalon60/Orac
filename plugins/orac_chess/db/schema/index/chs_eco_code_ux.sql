--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Provide the complete ECO code reference.
-- Purpose: Supply installation-owned reference descriptions.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_index context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_objects where owner='ORAC_CHESS' and object_name='CHS_ECO_CODE_UX'
create unique index orac_chess.chs_eco_code_ux on orac_chess.chess_eco_code (eco_code);
--rollback drop index orac_chess.chs_eco_code_ux;
