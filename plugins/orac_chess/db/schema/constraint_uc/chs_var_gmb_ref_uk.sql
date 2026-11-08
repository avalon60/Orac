--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs var gmb ref uk.
-- Purpose: Install the constraint_uc object chs_var_gmb_ref_uk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_uc_chs_var_gmb_ref_uk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_VAR_GMB_REF_UK'
alter table orac_chess.chess_variation add constraint chs_var_gmb_ref_uk unique (variation_id, gambit_id) using index orac_chess.chs_var_gmb_ref_ux;

--rollback alter table orac_chess.chess_variation drop constraint chs_var_gmb_ref_uk;
