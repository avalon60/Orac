--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_variation and its columns.
-- Purpose: Install the comment object chess_variation in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_variation context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_variation is 'Named complete PGN lines for one opening or gambit, including branches.';
comment on column orac_chess.chess_variation.variation_id is 'Variation id for chess variation.';
comment on column orac_chess.chess_variation.opening_id is 'Opening id for chess variation.';
comment on column orac_chess.chess_variation.gambit_id is 'Gambit id for chess variation.';
comment on column orac_chess.chess_variation.parent_variation_id is 'Parent variation id for chess variation.';
comment on column orac_chess.chess_variation.branch_ply is 'Number of shared parent mainline half-moves before the first differing move; zero branches before the first move.';
comment on column orac_chess.chess_variation.variation_type is 'Derived ownership type: O for opening, G for gambit; never supplied by a writer.';
comment on column orac_chess.chess_variation.name is 'Name for chess variation.';
comment on column orac_chess.chess_variation.line_kind is 'Line kind for chess variation.';
comment on column orac_chess.chess_variation.pgn is 'Authoritative Portable Game Notation move sequence; chess legality is validated by future application code.';
comment on column orac_chess.chess_variation.starting_fen is 'Optional non-standard position before the root variation PGN begins.';
comment on column orac_chess.chess_variation.annotation is 'Annotation for chess variation.';

--rollback comment on table orac_chess.chess_variation is '';
--rollback comment on column orac_chess.chess_variation.variation_id is '';
--rollback comment on column orac_chess.chess_variation.opening_id is '';
--rollback comment on column orac_chess.chess_variation.gambit_id is '';
--rollback comment on column orac_chess.chess_variation.parent_variation_id is '';
--rollback comment on column orac_chess.chess_variation.branch_ply is '';
--rollback comment on column orac_chess.chess_variation.name is '';
--rollback comment on column orac_chess.chess_variation.line_kind is '';
--rollback comment on column orac_chess.chess_variation.pgn is '';
--rollback comment on column orac_chess.chess_variation.starting_fen is '';
--rollback comment on column orac_chess.chess_variation.annotation is '';
--rollback comment on column orac_chess.chess_variation.variation_type is '';
