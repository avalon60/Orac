--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_commentary and its columns.
-- Purpose: Install the comment object chess_commentary in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_commentary context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_commentary is 'Historical or instructional prose owned by exactly one chess subject.';
comment on column orac_chess.chess_commentary.commentary_id is 'Commentary id for chess commentary.';
comment on column orac_chess.chess_commentary.opening_id is 'Opening id for chess commentary.';
comment on column orac_chess.chess_commentary.gambit_id is 'Gambit id for chess commentary.';
comment on column orac_chess.chess_commentary.variation_id is 'Variation id for chess commentary.';
comment on column orac_chess.chess_commentary.commentary_kind is 'Commentary kind for chess commentary.';
comment on column orac_chess.chess_commentary.title is 'Title for chess commentary.';
comment on column orac_chess.chess_commentary.content is 'Content for chess commentary.';

--rollback comment on table orac_chess.chess_commentary is '';
--rollback comment on column orac_chess.chess_commentary.commentary_id is '';
--rollback comment on column orac_chess.chess_commentary.opening_id is '';
--rollback comment on column orac_chess.chess_commentary.gambit_id is '';
--rollback comment on column orac_chess.chess_commentary.variation_id is '';
--rollback comment on column orac_chess.chess_commentary.commentary_kind is '';
--rollback comment on column orac_chess.chess_commentary.title is '';
--rollback comment on column orac_chess.chess_commentary.content is '';
