--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_variation_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_variation_v as
select variation_id, opening_id, gambit_id, variation_type, parent_variation_id, branch_ply, name, line_kind, pgn, starting_fen, annotation, row_version
from orac_chess.chess_variation;
--rollback drop view orac_chess.chess_variation_v;
