--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Describe only approved query projection semantics.
-- Purpose: Keep generated queries faithful to explicit Chess relationships.
-- Usage: Managed plugin lifecycle controller 16_query_reference.xml.

--changeset clive:orac_chess_query_metadata context:plugin,prod labels:plugin stripComments:false runOnChange:true
comment on table orac_chess.chess_query_opening_v is 'OPENING and SYSTEM share explicit opening relationships. Parent opening is an opening hierarchy, never a variation hierarchy.';
comment on table orac_chess.chess_query_opening_alias_v is 'Aliases identify an existing opening. Alias spelling is not a separate opening or an ECO description.';
comment on table orac_chess.chess_query_gambit_v is 'Gambits have independent identity and can be linked to multiple openings through opening_gambit.';
comment on table orac_chess.chess_query_opening_gambit_v is 'Explicit many-to-many opening and gambit associations. Do not infer relationships from names.';
comment on table orac_chess.chess_query_opening_eco_v is 'Explicit opening ECO associations; multiple ECO rows may belong to an opening. No row means no recorded ECO.';
comment on table orac_chess.chess_query_gambit_eco_v is 'Explicit gambit ECO associations; do not inherit ECO from associated openings.';
comment on table orac_chess.chess_query_variation_eco_v is 'Explicit variation ECO associations; do not infer inherited or transposed ECO.';
comment on table orac_chess.chess_query_eco_code_v is 'Upstream ECO catalogue descriptions are upstream names, not canonical Orac opening names. No transposition equivalence is encoded.';
comment on table orac_chess.chess_query_variation_v is 'Variation ownership is exactly one opening_id or gambit_id; variation_type O or G derives from that owner. Parent variation must retain the same owner; composite relationships preserve ownership. branch_ply is an explicit branch position, not proof of transposition. line_kind is an instructional line classification.';
comment on column orac_chess.chess_query_opening_v.opening_type is 'OPENING or SYSTEM; both share opening relationships.';
comment on column orac_chess.chess_query_variation_v.variation_type is 'Derived owner type O for opening, G for gambit. Exactly one owner applies.';
--rollback comment on table orac_chess.chess_query_opening_v is '';
--rollback comment on table orac_chess.chess_query_opening_alias_v is '';
--rollback comment on table orac_chess.chess_query_gambit_v is '';
--rollback comment on table orac_chess.chess_query_opening_gambit_v is '';
--rollback comment on table orac_chess.chess_query_opening_eco_v is '';
--rollback comment on table orac_chess.chess_query_gambit_eco_v is '';
--rollback comment on table orac_chess.chess_query_variation_eco_v is '';
--rollback comment on table orac_chess.chess_query_eco_code_v is '';
--rollback comment on table orac_chess.chess_query_variation_v is '';
--rollback comment on column orac_chess.chess_query_opening_v.opening_type is '';
--rollback comment on column orac_chess.chess_query_variation_v.variation_type is '';
