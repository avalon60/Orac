--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_concept_variation and its columns.
-- Purpose: Install the comment object chess_concept_variation in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_concept_variation context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_concept_variation is 'Concept associations to variations.';
comment on column orac_chess.chess_concept_variation.concept_id is 'Concept id for chess concept variation.';
comment on column orac_chess.chess_concept_variation.variation_id is 'Variation id for chess concept variation.';

--rollback comment on table orac_chess.chess_concept_variation is '';
--rollback comment on column orac_chess.chess_concept_variation.concept_id is '';
--rollback comment on column orac_chess.chess_concept_variation.variation_id is '';
