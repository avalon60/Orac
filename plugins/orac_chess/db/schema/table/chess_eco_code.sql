--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Provide the complete ECO code reference.
-- Purpose: Supply installation-owned reference descriptions.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_eco_table context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_objects where owner='ORAC_CHESS' and object_name='CHESS_ECO_CODE'
create table orac_chess.chess_eco_code (
  eco_code varchar2(3 char) not null,
  description clob not null
);
--rollback drop table orac_chess.chess_eco_code;
