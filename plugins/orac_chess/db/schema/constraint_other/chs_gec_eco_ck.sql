--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_gambit_eco_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name=upper('chs_gec_eco_ck')
alter table orac_chess.chess_gambit_eco add constraint chs_gec_eco_ck check (regexp_like(eco_code, '^[A-E][0-9]{2}$', 'c'));
--rollback select 1/0 from dual;
