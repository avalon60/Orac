--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs var branch ck.
-- Purpose: Install the constraint_other object chs_var_branch_ck in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_other_chs_var_branch_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_VAR_BRANCH_CK'
alter table orac_chess.chess_variation add constraint chs_var_branch_ck check ((parent_variation_id is null and branch_ply is null and line_kind = 'MAIN') or (parent_variation_id is not null and branch_ply is not null and line_kind = 'ALTERNATIVE' and starting_fen is null));

--rollback alter table orac_chess.chess_variation drop constraint chs_var_branch_ck;
