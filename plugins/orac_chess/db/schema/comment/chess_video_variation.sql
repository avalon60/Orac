--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_video_variation and its columns.
-- Purpose: Install the comment object chess_video_variation in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_video_variation context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_video_variation is 'Video associations to specific named move lines.';
comment on column orac_chess.chess_video_variation.video_id is 'Video id for chess video variation.';
comment on column orac_chess.chess_video_variation.variation_id is 'Variation id for chess video variation.';

--rollback comment on table orac_chess.chess_video_variation is '';
--rollback comment on column orac_chess.chess_video_variation.video_id is '';
--rollback comment on column orac_chess.chess_video_variation.variation_id is '';
