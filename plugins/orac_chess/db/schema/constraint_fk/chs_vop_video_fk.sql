--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs vop video fk.
-- Purpose: Install the constraint_fk object chs_vop_video_fk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_fk_chs_vop_video_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_VOP_VIDEO_FK'
alter table orac_chess.chess_video_opening add constraint chs_vop_video_fk foreign key (video_id) references orac_chess.chess_video (video_id);

--rollback alter table orac_chess.chess_video_opening drop constraint chs_vop_video_fk;
