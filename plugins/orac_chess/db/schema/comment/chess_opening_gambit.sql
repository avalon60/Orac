--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_opening_gambit and its columns.
-- Purpose: Install the comment object chess_opening_gambit in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_opening_gambit context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_opening_gambit is 'Many-to-many classification of gambits within openings.';
comment on column orac_chess.chess_opening_gambit.opening_id is 'Opening id for chess opening gambit.';
comment on column orac_chess.chess_opening_gambit.gambit_id is 'Gambit id for chess opening gambit.';

--rollback comment on table orac_chess.chess_opening_gambit is '';
--rollback comment on column orac_chess.chess_opening_gambit.opening_id is '';
--rollback comment on column orac_chess.chess_opening_gambit.gambit_id is '';
