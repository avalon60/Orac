--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs cmt kind ck.
-- Purpose: Install the constraint_other object chs_cmt_kind_ck in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_other_chs_cmt_kind_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_CMT_KIND_CK'
alter table orac_chess.chess_commentary add constraint chs_cmt_kind_ck check (commentary_kind in ('HISTORY','STRATEGY','PRACTITIONER','MISTAKE','FACT','INSTRUCTION'));

--rollback alter table orac_chess.chess_commentary drop constraint chs_cmt_kind_ck;
