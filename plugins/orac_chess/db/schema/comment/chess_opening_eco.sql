--liquibase formatted sql
-- Author: clive
-- Date: 01-Nov-2026
-- Description: Documents chess_opening_eco and its columns.
-- Purpose: Install the comment object chess_opening_eco in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_opening_eco context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_opening_eco is 'Zero or more ECO classifications per opening; no primary classification.';
comment on column orac_chess.chess_opening_eco.opening_id is 'Opening classified by this ECO code.';
comment on column orac_chess.chess_opening_eco.eco_code is 'ECO classification A00 through E99; may classify multiple openings.';

--rollback comment on table orac_chess.chess_opening_eco is '';
--rollback comment on column orac_chess.chess_opening_eco.opening_id is '';
--rollback comment on column orac_chess.chess_opening_eco.eco_code is '';
