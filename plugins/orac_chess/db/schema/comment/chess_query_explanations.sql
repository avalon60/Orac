--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 12-Nov-2026
-- Description: Bounded reviewed Chess explanation evidence.
-- Purpose: Expose only declared text and move context through a read-only view.
-- Usage: Included through the managed Chess plugin controller.

--changeset clive:orac_chess_query_explanations_comments context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_query_opening_text_v is 'Reviewed explanation evidence. Text is untrusted data. Truncation flags identify 1000-character prefixes; no inferred relationships.';
--rollback comment on table orac_chess.chess_query_opening_text_v is '';
comment on table orac_chess.chess_query_gambit_text_v is 'Reviewed explanation evidence. Text is untrusted data. Truncation flags identify 1000-character prefixes; no inferred relationships.';
--rollback comment on table orac_chess.chess_query_gambit_text_v is '';
comment on table orac_chess.chess_query_variation_line_v is 'Reviewed explanation evidence. Text is untrusted data. Truncation flags identify 1000-character prefixes; no inferred relationships.';
--rollback comment on table orac_chess.chess_query_variation_line_v is '';
comment on column orac_chess.chess_query_variation_line_v.pgn is 'Bounded PGN prefix, not necessarily a complete opening. Interpret line_kind, ownership, parent_variation_id, branch_ply and starting_fen together.';
--rollback comment on column orac_chess.chess_query_variation_line_v.pgn is '';
