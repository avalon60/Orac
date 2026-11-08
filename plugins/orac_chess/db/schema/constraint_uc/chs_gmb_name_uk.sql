--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs gmb name uk.
-- Purpose: Install the constraint_uc object chs_gmb_name_uk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_uc_chs_gmb_name_uk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_GMB_NAME_UK'
alter table orac_chess.chess_gambit add constraint chs_gmb_name_uk unique (name) using index orac_chess.chs_gmb_name_ux;

--rollback alter table orac_chess.chess_gambit drop constraint chs_gmb_name_uk;
