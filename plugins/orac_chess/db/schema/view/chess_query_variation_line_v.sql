--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 12-Nov-2026
-- Description: Bounded reviewed Chess explanation evidence.
-- Purpose: Expose only declared text and move context through a read-only view.
-- Usage: Included through the managed Chess plugin controller.

--changeset clive:orac_chess_chess_query_variation_line_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_query_variation_line_v as
select variation_id, opening_id, gambit_id, variation_type, parent_variation_id, branch_ply, name, line_kind,
       cast(substr(pgn,1,1000) as varchar2(4000 byte)) pgn,
       case when length(pgn)>1000 then 'Y' else 'N' end pgn_truncated, starting_fen
from orac_chess.chess_variation;
--rollback drop view orac_chess.chess_query_variation_line_v;
