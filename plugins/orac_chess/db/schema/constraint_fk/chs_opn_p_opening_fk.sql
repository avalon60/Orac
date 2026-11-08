--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs opn p opening fk.
-- Purpose: Install the constraint_fk object chs_opn_p_opening_fk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_fk_chs_opn_p_opening_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_OPN_P_OPENING_FK'
alter table orac_chess.chess_opening add constraint chs_opn_p_opening_fk foreign key (parent_opening_id) references orac_chess.chess_opening (opening_id);

--rollback alter table orac_chess.chess_opening drop constraint chs_opn_p_opening_fk;
