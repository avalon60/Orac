--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_validation_api_spec context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package orac_chess.chess_validation_api authid definer as
  -- Serializes aggregate changes and hierarchy checks until caller commit/rollback.
  -- Private validation operation; never granted to the APEX parsing schema.
  procedure lock_control;
  -- Private validation operation; never granted to the APEX parsing schema.
  procedure require_version(p_actual number, p_expected number);
  -- Private validation operation; never granted to the APEX parsing schema.
  procedure validate_url(p_url varchar2);
  -- Private validation operation; never granted to the APEX parsing schema.
  procedure validate_opening(p_id number, p_parent_id number);
  -- Private validation operation; never granted to the APEX parsing schema.
  procedure validate_pgn(p_pgn clob, p_single_line boolean, p_fen varchar2 default null);
  -- Read a header only after authoritative complete PGN validation.
  function pgn_header(p_pgn clob,p_name varchar2) return varchar2;
  -- Private validation operation; never granted to the APEX parsing schema.
  procedure validate_branch(p_parent clob,p_child clob,p_ply number,p_fen varchar2);
  -- Private validation operation; never granted to the APEX parsing schema.
  procedure validate_variation_tree(p_id number);
  -- Private validation operation; never granted to the APEX parsing schema.
  procedure validate_image(p_content blob, p_mime varchar2, p_alt varchar2);

end chess_validation_api;
/
--rollback drop package orac_chess.chess_validation_api;
