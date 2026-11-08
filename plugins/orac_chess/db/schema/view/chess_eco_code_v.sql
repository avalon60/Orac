--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Provide the complete ECO code reference.
-- Purpose: Supply installation-owned reference descriptions.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_view context:plugin,prod labels:plugin stripComments:false runOnChange:true
create or replace view orac_chess.chess_eco_code_v as
select eco_code, description
from orac_chess.chess_eco_code;
--rollback drop view orac_chess.chess_eco_code_v;
