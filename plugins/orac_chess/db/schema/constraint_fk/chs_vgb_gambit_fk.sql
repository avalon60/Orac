--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs vgb gambit fk.
-- Purpose: Install the constraint_fk object chs_vgb_gambit_fk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_fk_chs_vgb_gambit_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_VGB_GAMBIT_FK'
alter table orac_chess.chess_video_gambit add constraint chs_vgb_gambit_fk foreign key (gambit_id) references orac_chess.chess_gambit (gambit_id);

--rollback alter table orac_chess.chess_video_gambit drop constraint chs_vgb_gambit_fk;
