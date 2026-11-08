--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_image_opening and its columns.
-- Purpose: Install the comment object chess_image_opening in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_image_opening context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_image_opening is 'Image associations to openings.';
comment on column orac_chess.chess_image_opening.image_id is 'Image id for chess image opening.';
comment on column orac_chess.chess_image_opening.opening_id is 'Opening id for chess image opening.';

--rollback comment on table orac_chess.chess_image_opening is '';
--rollback comment on column orac_chess.chess_image_opening.image_id is '';
--rollback comment on column orac_chess.chess_image_opening.opening_id is '';
