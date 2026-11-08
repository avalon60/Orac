--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_image and its columns.
-- Purpose: Install the comment object chess_image in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_image context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_image is 'Optional supplemental image bytes and accessibility metadata.';
comment on column orac_chess.chess_image.image_id is 'Image id for chess image.';
comment on column orac_chess.chess_image.image_content is 'Supplemental image bytes, not a generated board position.';
comment on column orac_chess.chess_image.filename is 'Filename for chess image.';
comment on column orac_chess.chess_image.mime_type is 'Mime type for chess image.';
comment on column orac_chess.chess_image.description is 'Description for chess image.';
comment on column orac_chess.chess_image.accessibility_text is 'Accessibility text for chess image.';

--rollback comment on table orac_chess.chess_image is '';
--rollback comment on column orac_chess.chess_image.image_id is '';
--rollback comment on column orac_chess.chess_image.image_content is '';
--rollback comment on column orac_chess.chess_image.filename is '';
--rollback comment on column orac_chess.chess_image.mime_type is '';
--rollback comment on column orac_chess.chess_image.description is '';
--rollback comment on column orac_chess.chess_image.accessibility_text is '';
