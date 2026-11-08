--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_CSR_PK'
alter table orac_chess.chess_content_source add constraint chs_csr_pk primary key (creator) using index orac_chess.chs_csr_creator_ux;
--rollback alter table orac_chess.chess_content_source drop constraint chs_csr_pk keep index;
