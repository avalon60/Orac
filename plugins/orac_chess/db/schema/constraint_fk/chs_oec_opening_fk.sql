--liquibase formatted sql
-- Author: clive
-- Date: 01-Nov-2026
-- Description: chs oec opening fk.
-- Purpose: Install the constraint_fk object chs_oec_opening_fk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_fk_chs_oec_opening_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_OEC_OPENING_FK'
alter table orac_chess.chess_opening_eco add constraint chs_oec_opening_fk foreign key (opening_id) references orac_chess.chess_opening (opening_id);

--rollback alter table orac_chess.chess_opening_eco drop constraint chs_oec_opening_fk;
