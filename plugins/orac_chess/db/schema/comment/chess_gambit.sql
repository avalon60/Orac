--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_gambit and its columns.
-- Purpose: Install the comment object chess_gambit in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_gambit context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_gambit is 'Named gambit identity, independent of the openings that contain it.';
comment on column orac_chess.chess_gambit.gambit_id is 'Gambit id for chess gambit.';
comment on column orac_chess.chess_gambit.name is 'Name for chess gambit.';
comment on column orac_chess.chess_gambit.description is 'Description for chess gambit.';

--rollback comment on table orac_chess.chess_gambit is '';
--rollback comment on column orac_chess.chess_gambit.gambit_id is '';
--rollback comment on column orac_chess.chess_gambit.name is '';
--rollback comment on column orac_chess.chess_gambit.description is '';
