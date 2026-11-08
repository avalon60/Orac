--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_variation_api_spec context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package orac_chess.chess_variation_api authid definer as
  -- Insert when p_id is null; otherwise require the observed version. Return the new version.
  procedure save_variation(p_id in out number, p_expected_version in number, p_opening_id in number, p_gambit_id in number, p_parent_variation_id in number, p_branch_ply in number, p_name in varchar2, p_line_kind in varchar2, p_pgn in clob, p_starting_fen in varchar2, p_annotation in clob, p_new_version out number);
  -- Require the observed version and reject referenced rows; caller owns commit/rollback.
  procedure delete_variation(p_id number, p_expected_version number);

end chess_variation_api;
/
--rollback drop package orac_chess.chess_variation_api;
