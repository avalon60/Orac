--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: chs ivr image fk.
-- Purpose: Install the constraint_fk object chs_ivr_image_fk in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_constraint_fk_chs_ivr_image_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CHESS' and constraint_name = 'CHS_IVR_IMAGE_FK'
alter table orac_chess.chess_image_variation add constraint chs_ivr_image_fk foreign key (image_id) references orac_chess.chess_image (image_id);

--rollback alter table orac_chess.chess_image_variation drop constraint chs_ivr_image_fk;
