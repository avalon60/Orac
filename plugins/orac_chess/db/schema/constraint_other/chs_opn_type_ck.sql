--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Nov-2026
-- Description: Restricts the opening classification to OPENING or SYSTEM.
-- Purpose: Install the CHS_OPN_TYPE_CK check in the ORAC_CHESS fresh baseline.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_other_chs_opn_type_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and table_name = 'CHESS_OPENING' and constraint_name = 'CHS_OPN_TYPE_CK'
alter table orac_chess.chess_opening add constraint chs_opn_type_ck check (opening_type in ('OPENING', 'SYSTEM'));

--rollback alter table orac_chess.chess_opening drop constraint chs_opn_type_ck;
