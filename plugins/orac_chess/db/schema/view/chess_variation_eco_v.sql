--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_variation_view context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_objects where owner='ORAC_CHESS' and object_name=upper('chess_variation_eco_v')
create or replace view orac_chess.chess_variation_eco_v as
select variation_id, eco_code from orac_chess.chess_variation_eco;
--rollback drop view orac_chess.chess_variation_eco_v;
