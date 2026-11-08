--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs con category ck.
-- Purpose: Install the constraint_other object chs_con_category_ck in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_other_chs_con_category_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_CON_CATEGORY_CK'
alter table orac_chess.chess_concept add constraint chs_con_category_ck check (category_code in ('TACTIC','STRATEGY','STRUCTURE','MATE_PATTERN','OTHER'));

--rollback alter table orac_chess.chess_concept drop constraint chs_con_category_ck;
