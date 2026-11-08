--liquibase formatted sql
-- Author: clive
-- Date: 25-Oct-2026
-- Description: Documents chess_concept and its columns.
-- Purpose: Install the comment object chess_concept in ORAC_CHESS.
-- Usage: Included by db/liquibase/pluginController.xml through the managed Orac plugin installer.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:orac_chess_comment_chess_concept context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_concept is 'Reusable tactical or strategic chess concepts.';
comment on column orac_chess.chess_concept.concept_id is 'Concept id for chess concept.';
comment on column orac_chess.chess_concept.concept_code is 'Concept code for chess concept.';
comment on column orac_chess.chess_concept.name is 'Name for chess concept.';
comment on column orac_chess.chess_concept.category_code is 'Category code for chess concept.';
comment on column orac_chess.chess_concept.description is 'Description for chess concept.';

--rollback comment on table orac_chess.chess_concept is '';
--rollback comment on column orac_chess.chess_concept.concept_id is '';
--rollback comment on column orac_chess.chess_concept.concept_code is '';
--rollback comment on column orac_chess.chess_concept.name is '';
--rollback comment on column orac_chess.chess_concept.category_code is '';
--rollback comment on column orac_chess.chess_concept.description is '';
