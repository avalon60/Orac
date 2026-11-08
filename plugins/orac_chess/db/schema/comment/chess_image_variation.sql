--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_image_variation and its columns.
-- Purpose: Install the comment object chess_image_variation in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_image_variation context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_image_variation is 'Image associations to variations.';
comment on column orac_chess.chess_image_variation.image_id is 'Image id for chess image variation.';
comment on column orac_chess.chess_image_variation.variation_id is 'Variation id for chess image variation.';

--rollback comment on table orac_chess.chess_image_variation is '';
--rollback comment on column orac_chess.chess_image_variation.image_id is '';
--rollback comment on column orac_chess.chess_image_variation.variation_id is '';
