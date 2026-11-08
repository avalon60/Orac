--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_opening_alias_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_opening_alias_v as
select opening_alias_id, opening_id, alias_name
from orac_chess.chess_opening_alias;
--rollback drop view orac_chess.chess_opening_alias_v;
