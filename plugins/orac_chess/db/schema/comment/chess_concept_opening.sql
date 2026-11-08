--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_concept_opening and its columns.
-- Purpose: Install the comment object chess_concept_opening in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_concept_opening context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_concept_opening is 'Concept associations to openings.';
comment on column orac_chess.chess_concept_opening.concept_id is 'Concept id for chess concept opening.';
comment on column orac_chess.chess_concept_opening.opening_id is 'Opening id for chess concept opening.';

--rollback comment on table orac_chess.chess_concept_opening is '';
--rollback comment on column orac_chess.chess_concept_opening.concept_id is '';
--rollback comment on column orac_chess.chess_concept_opening.opening_id is '';
