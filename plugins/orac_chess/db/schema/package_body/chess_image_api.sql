--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_image_api_body context:plugin,prod labels:plugin stripComments:false runOnChange:true endDelimiter:/
create or replace package body orac_chess.chess_image_api as
  procedure save_image(p_id in out number, p_expected_version in number, p_filename in varchar2, p_mime_type in varchar2, p_description in varchar2, p_accessibility_text in varchar2, p_image_content in blob, p_new_version out number) is
  begin
    chess_admin_tapi.save_image(p_id, p_expected_version, p_filename, p_mime_type, p_description, p_accessibility_text, p_image_content, p_new_version);
  end;
  procedure delete_image(p_id number, p_expected_version number) is
  begin
    chess_admin_tapi.delete_image(p_id,p_expected_version);
  end;
  procedure fetch_content(p_id number, p_content out blob, p_mime out varchar2, p_filename out varchar2) is
  begin
    select image_content,mime_type,filename into p_content,p_mime,p_filename from chess_image where image_id=p_id;
  exception
    when no_data_found then
      raise_application_error(-20008, 'Image does not exist.');
  end;

end chess_image_api;
/
--rollback drop package body orac_chess.chess_image_api;
