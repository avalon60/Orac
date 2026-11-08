--liquibase formatted sql
-- Author: clive
-- Date: 01-Nov-2026
-- Description: chs oec eco ck.
-- Purpose: Install the constraint_other object chs_oec_eco_ck in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_other_chs_oec_eco_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_OEC_ECO_CK'
alter table orac_chess.chess_opening_eco add constraint chs_oec_eco_ck check (regexp_like(eco_code, '^[A-E][0-9]{2}$'));

--rollback alter table orac_chess.chess_opening_eco drop constraint chs_oec_eco_ck;
