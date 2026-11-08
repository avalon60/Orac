--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs con code uk.
-- Purpose: Install the constraint_uc object chs_con_code_uk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_uc_chs_con_code_uk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_CON_CODE_UK'
alter table orac_chess.chess_concept add constraint chs_con_code_uk unique (concept_code) using index orac_chess.chs_con_code_ux;

--rollback alter table orac_chess.chess_concept drop constraint chs_con_code_uk;
