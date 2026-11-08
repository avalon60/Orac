--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_image_api_spec context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package orac_chess.chess_image_api authid definer as
  -- Insert when p_id is null; otherwise require the observed version. Return the new version.
  procedure save_image(p_id in out number, p_expected_version in number, p_filename in varchar2, p_mime_type in varchar2, p_description in varchar2, p_accessibility_text in varchar2, p_image_content in blob, p_new_version out number);
  -- Require the observed version and reject referenced rows; caller owns commit/rollback.
  procedure delete_image(p_id number, p_expected_version number);
  -- Fetch bytes only through this controlled entrypoint; caller must authorize delivery.
  procedure fetch_content(p_id number, p_content out blob, p_mime out varchar2, p_filename out varchar2);

end chess_image_api;
/
--rollback drop package orac_chess.chess_image_api;
