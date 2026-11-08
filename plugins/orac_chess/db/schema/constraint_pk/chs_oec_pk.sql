--liquibase formatted sql
-- Author: clive
-- Date: 01-Nov-2026
-- Description: chs oec pk.
-- Purpose: Install the constraint_pk object chs_oec_pk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_pk_chs_oec_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_OEC_PK'
alter table orac_chess.chess_opening_eco add constraint chs_oec_pk primary key (opening_id, eco_code) using index orac_chess.chs_oec_pk_ix;

--rollback alter table orac_chess.chess_opening_eco drop constraint chs_oec_pk keep index;
