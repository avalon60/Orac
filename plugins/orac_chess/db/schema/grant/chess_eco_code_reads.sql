--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Provide the complete ECO code reference.
-- Purpose: Supply installation-owned reference descriptions.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_reads context:plugin,prod labels:plugin stripComments:false runOnChange:true
grant select on orac_chess.chess_eco_code_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_eco_code_v from orac_apx_pub;
