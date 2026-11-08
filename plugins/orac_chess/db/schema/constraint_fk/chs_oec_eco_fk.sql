--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_opening_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_OEC_ECO_FK'
alter table orac_chess.chess_opening_eco add constraint chs_oec_eco_fk foreign key (eco_code) references orac_chess.chess_eco_code (eco_code);
--rollback alter table orac_chess.chess_opening_eco drop constraint chs_oec_eco_fk;
