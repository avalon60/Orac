--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_gambit_subject_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name=upper('chs_gec_subject_fk')
alter table orac_chess.chess_gambit_eco add constraint chs_gec_subject_fk foreign key (gambit_id) references orac_chess.chess_gambit (gambit_id);
--rollback select 1/0 from dual;
