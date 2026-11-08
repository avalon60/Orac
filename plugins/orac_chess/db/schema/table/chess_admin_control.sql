--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_control_table context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tables where owner='ORAC_CHESS' and table_name='CHESS_ADMIN_CONTROL'
create table orac_chess.chess_admin_control (
  control_id number not null,
  max_image_bytes number default 10485760 not null
);
--rollback drop table orac_chess.chess_admin_control;
