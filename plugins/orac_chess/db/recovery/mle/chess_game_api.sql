--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_game_api_body context:plugin,prod labels:plugin stripComments:false runOnChange:true runAlways:true endDelimiter:/
create or replace package body orac_chess.chess_game_api as
  procedure save_game(p_id in out number, p_expected_version in number, p_white_player in varchar2, p_black_player in varchar2, p_event_name in varchar2, p_site in varchar2, p_game_date in date, p_result_code in varchar2, p_eco_code in varchar2, p_opening_id in number, p_pgn in clob, p_source_url in varchar2, p_commentary in clob, p_new_version out number) is
  begin
raise_application_error(-20020,'Chess PGN maintenance is unavailable: runtime withdrawn.');
  end;
  procedure delete_game(p_id number, p_expected_version number) is
  begin
raise_application_error(-20020,'Chess PGN maintenance is unavailable: runtime withdrawn.');
  end;

  function pgn_header(p_pgn clob,p_name varchar2) return varchar2 is
  begin
    chess_validation_api.validate_pgn(p_pgn,false);
    return chess_validation_api.pgn_header(p_pgn,p_name);
  end;
end chess_game_api;
/
--rollback drop package body orac_chess.chess_game_api;
