--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_control_seed context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from orac_chess.chess_admin_control
insert into orac_chess.chess_admin_control (control_id,max_image_bytes) values (1,10485760);
--rollback delete from orac_chess.chess_admin_control where control_id=1;
