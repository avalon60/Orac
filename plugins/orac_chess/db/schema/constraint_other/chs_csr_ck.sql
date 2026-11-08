--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_checks context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_CSR_CREATOR_CK'
alter table orac_chess.chess_content_source add constraint chs_csr_creator_ck check (trim(creator) is not null);
--rollback alter table orac_chess.chess_content_source drop constraint chs_csr_creator_ck;

--changeset clive:orac_chess_content_source_version_check context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner='ORAC_CHESS' and constraint_name='CHS_CSR_VERSION_CK'
alter table orac_chess.chess_content_source add constraint chs_csr_version_ck check (row_version >= 1 and row_version = trunc(row_version));
--rollback alter table orac_chess.chess_content_source drop constraint chs_csr_version_ck;
