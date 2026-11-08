--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Add explicit ECO relationships without changing existing assignments.
-- Purpose: Extend Chess ECO ownership through an additive upgrade.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_ext_gambit_table context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_objects where owner='ORAC_CHESS' and object_name=upper('chess_gambit_eco')
create table orac_chess.chess_gambit_eco (
  gambit_id number not null,
  eco_code varchar2(3 char) not null
);
--rollback select 1/0 from dual;
