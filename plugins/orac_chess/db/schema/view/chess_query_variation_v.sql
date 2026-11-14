--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Expose only the approved reference query projection.
-- Purpose: Install a separate read-only Chess query view.
-- Usage: Included by the managed plugin controller.

--changeset clive:orac_chess_query_variation_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_query_variation_v as
select variation_id, opening_id, gambit_id, variation_type, parent_variation_id, branch_ply, name, line_kind
from orac_chess.chess_variation;
--rollback drop view orac_chess.chess_query_variation_v;
