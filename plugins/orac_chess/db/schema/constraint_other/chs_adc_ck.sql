--liquibase formatted sql
-- Author: clive
-- Date: 02-Nov-2026
-- Description: Installs the Chess administration contract.
-- Purpose: Add approved private maintenance objects without changing baseline history.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_admin_control_check context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_ADC_CK'
alter table orac_chess.chess_admin_control add constraint chs_adc_ck check (control_id = 1 and max_image_bytes > 0 and max_image_bytes = trunc(max_image_bytes));
--rollback alter table orac_chess.chess_admin_control drop constraint chs_adc_ck;
