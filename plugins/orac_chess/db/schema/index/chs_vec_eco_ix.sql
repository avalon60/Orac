--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_variation_reverse_index context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_objects where owner='ORAC_CHESS' and object_name='CHS_VEC_ECO_IX'
create index orac_chess.chs_vec_eco_ix on orac_chess.chess_variation_eco (eco_code, variation_id);
--rollback drop index orac_chess.chs_vec_eco_ix;
