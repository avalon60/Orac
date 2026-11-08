--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_opening and its columns.
-- Purpose: Install the comment object chess_opening in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_opening context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_opening is 'Recognised opening identity and its optional parent in an opening family.';
comment on column orac_chess.chess_opening.opening_id is 'Opening id for chess opening.';
comment on column orac_chess.chess_opening.name is 'Name for chess opening.';
comment on column orac_chess.chess_opening.opening_type is 'Classification as OPENING or SYSTEM; both share opening relationships. Defaults to OPENING.';
comment on column orac_chess.chess_opening.description is 'Description for chess opening.';
comment on column orac_chess.chess_opening.parent_opening_id is 'Parent opening id for chess opening.';

--rollback comment on table orac_chess.chess_opening is '';
--rollback comment on column orac_chess.chess_opening.opening_id is '';
--rollback comment on column orac_chess.chess_opening.name is '';
--rollback comment on column orac_chess.chess_opening.opening_type is '';
--rollback comment on column orac_chess.chess_opening.description is '';
--rollback comment on column orac_chess.chess_opening.parent_opening_id is '';
