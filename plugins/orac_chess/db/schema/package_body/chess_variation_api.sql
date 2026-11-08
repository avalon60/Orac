--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_variation_api_body context:plugin,prod labels:plugin stripComments:false runOnChange:true runAlways:true endDelimiter:/
create or replace package body orac_chess.chess_variation_api as
  procedure save_variation(p_id in out number, p_expected_version in number, p_opening_id in number, p_gambit_id in number, p_parent_variation_id in number, p_branch_ply in number, p_name in varchar2, p_line_kind in varchar2, p_pgn in clob, p_starting_fen in varchar2, p_annotation in clob, p_new_version out number) is
  begin
    chess_admin_tapi.save_variation(p_id,p_expected_version,p_opening_id,p_gambit_id,p_parent_variation_id,p_branch_ply,p_name,p_line_kind,p_pgn,p_starting_fen,p_annotation,p_new_version);
  end;
  procedure delete_variation(p_id number, p_expected_version number) is
  begin
    chess_admin_tapi.delete_variation(p_id,p_expected_version);
  end;

end chess_variation_api;
/
--rollback drop package body orac_chess.chess_variation_api;
