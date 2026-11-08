--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_variation_grant context:plugin,prod labels:plugin stripComments:false
grant select on orac_chess.chess_variation_eco_v to orac_apx_pub;
--rollback revoke select on orac_chess.chess_variation_eco_v from orac_apx_pub;
