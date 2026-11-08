--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_game_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_game_v as
select game_id, white_player, black_player, event_name, site, game_date, result_code, eco_code, opening_id, pgn, source_url, commentary, row_version
from orac_chess.chess_game;
--rollback drop view orac_chess.chess_game_v;
