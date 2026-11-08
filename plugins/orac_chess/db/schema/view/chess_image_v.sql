--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_image_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_image_v as
select image_id, filename, mime_type, description, accessibility_text, row_version, dbms_lob.getlength(image_content) as image_bytes
from orac_chess.chess_image;
--rollback drop view orac_chess.chess_image_v;
