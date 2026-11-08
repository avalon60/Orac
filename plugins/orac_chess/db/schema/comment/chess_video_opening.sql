--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_video_opening and its columns.
-- Purpose: Install the comment object chess_video_opening in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_video_opening context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_video_opening is 'Video associations to openings.';
comment on column orac_chess.chess_video_opening.video_id is 'Video id for chess video opening.';
comment on column orac_chess.chess_video_opening.opening_id is 'Opening id for chess video opening.';

--rollback comment on table orac_chess.chess_video_opening is '';
--rollback comment on column orac_chess.chess_video_opening.video_id is '';
--rollback comment on column orac_chess.chess_video_opening.opening_id is '';
