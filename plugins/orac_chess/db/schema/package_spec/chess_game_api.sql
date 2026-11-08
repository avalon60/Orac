--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_game_api_spec context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package orac_chess.chess_game_api authid definer as
  -- Insert when p_id is null; otherwise require the observed version. Return the new version.
  procedure save_game(p_id in out number, p_expected_version in number, p_white_player in varchar2, p_black_player in varchar2, p_event_name in varchar2, p_site in varchar2, p_game_date in date, p_result_code in varchar2, p_eco_code in varchar2, p_opening_id in number, p_pgn in clob, p_source_url in varchar2, p_commentary in clob, p_new_version out number);
  -- Require the observed version and reject referenced rows; caller owns commit/rollback.
  procedure delete_game(p_id number, p_expected_version number);

  -- Read a validated PGN header; unavailable while the authoritative PGN gate is blocked.
  function pgn_header(p_pgn clob,p_name varchar2) return varchar2;
end chess_game_api;
/
--rollback drop package orac_chess.chess_game_api;
