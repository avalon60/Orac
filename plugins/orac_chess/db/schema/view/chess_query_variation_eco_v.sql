--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 08-Nov-2026
-- Description: Expose only the approved reference query projection.
-- Purpose: Install a separate read-only Chess query view.
-- Usage: Included by the managed plugin controller.

--changeset clive:orac_chess_query_variation_eco_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_query_variation_eco_v as
select variation_id, eco_code
from orac_chess.chess_variation_eco;
--rollback drop view orac_chess.chess_query_variation_eco_v;
