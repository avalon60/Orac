--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_concept_gambit and its columns.
-- Purpose: Install the comment object chess_concept_gambit in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_concept_gambit context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_concept_gambit is 'Concept associations to gambits.';
comment on column orac_chess.chess_concept_gambit.concept_id is 'Concept id for chess concept gambit.';
comment on column orac_chess.chess_concept_gambit.gambit_id is 'Gambit id for chess concept gambit.';

--rollback comment on table orac_chess.chess_concept_gambit is '';
--rollback comment on column orac_chess.chess_concept_gambit.concept_id is '';
--rollback comment on column orac_chess.chess_concept_gambit.gambit_id is '';
