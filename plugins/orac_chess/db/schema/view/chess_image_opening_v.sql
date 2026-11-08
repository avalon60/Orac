--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_image_opening_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_image_opening_v as
select image_id, opening_id
from orac_chess.chess_image_opening;
--rollback drop view orac_chess.chess_image_opening_v;
