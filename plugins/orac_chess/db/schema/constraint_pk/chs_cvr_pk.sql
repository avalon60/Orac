--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs cvr pk.
-- Purpose: Install the constraint_pk object chs_cvr_pk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_pk_chs_cvr_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_CVR_PK'
alter table orac_chess.chess_concept_variation add constraint chs_cvr_pk primary key (concept_id, variation_id) using index orac_chess.chs_cvr_pk_ix;

--rollback alter table orac_chess.chess_concept_variation drop constraint chs_cvr_pk;
