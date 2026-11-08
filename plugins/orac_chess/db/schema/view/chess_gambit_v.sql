--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_chess_gambit_v context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_gambit_v as
select gambit_id, name, description, row_version
from orac_chess.chess_gambit;
--rollback drop view orac_chess.chess_gambit_v;
