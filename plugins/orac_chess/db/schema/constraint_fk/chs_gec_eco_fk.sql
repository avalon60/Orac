--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_gambit_eco_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name=upper('chs_gec_eco_fk')
alter table orac_chess.chess_gambit_eco add constraint chs_gec_eco_fk foreign key (eco_code) references orac_chess.chess_eco_code (eco_code);
--rollback select 1/0 from dual;
