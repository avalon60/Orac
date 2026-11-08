--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs opn parent ck.
-- Purpose: Install the constraint_other object chs_opn_parent_ck in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_other_chs_opn_parent_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_OPN_PARENT_CK'
alter table orac_chess.chess_opening add constraint chs_opn_parent_ck check (parent_opening_id is null or parent_opening_id <> opening_id);

--rollback alter table orac_chess.chess_opening drop constraint chs_opn_parent_ck;
