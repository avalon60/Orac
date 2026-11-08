--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_game and its columns.
-- Purpose: Install the comment object chess_game in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_game context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_game is 'Complete historical or instructional chess games, distinct from opening lines.';
comment on column orac_chess.chess_game.game_id is 'Game id for chess game.';
comment on column orac_chess.chess_game.white_player is 'White player for chess game.';
comment on column orac_chess.chess_game.black_player is 'Black player for chess game.';
comment on column orac_chess.chess_game.event_name is 'Event name for chess game.';
comment on column orac_chess.chess_game.site is 'Site for chess game.';
comment on column orac_chess.chess_game.game_date is 'Game date for chess game.';
comment on column orac_chess.chess_game.result_code is 'Result code for chess game.';
comment on column orac_chess.chess_game.eco_code is 'Eco code for chess game.';
comment on column orac_chess.chess_game.opening_id is 'Opening id for chess game.';
comment on column orac_chess.chess_game.pgn is 'Authoritative Portable Game Notation move sequence; chess legality is validated by future application code.';
comment on column orac_chess.chess_game.source_url is 'Source url for chess game.';
comment on column orac_chess.chess_game.commentary is 'Commentary for chess game.';

--rollback comment on table orac_chess.chess_game is '';
--rollback comment on column orac_chess.chess_game.game_id is '';
--rollback comment on column orac_chess.chess_game.white_player is '';
--rollback comment on column orac_chess.chess_game.black_player is '';
--rollback comment on column orac_chess.chess_game.event_name is '';
--rollback comment on column orac_chess.chess_game.site is '';
--rollback comment on column orac_chess.chess_game.game_date is '';
--rollback comment on column orac_chess.chess_game.result_code is '';
--rollback comment on column orac_chess.chess_game.eco_code is '';
--rollback comment on column orac_chess.chess_game.opening_id is '';
--rollback comment on column orac_chess.chess_game.pgn is '';
--rollback comment on column orac_chess.chess_game.source_url is '';
--rollback comment on column orac_chess.chess_game.commentary is '';
