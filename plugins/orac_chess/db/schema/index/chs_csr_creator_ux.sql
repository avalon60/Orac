--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Nov-2026
-- Description: Maintains Chess content source reference data.
-- Purpose: Provide creator identities without changing existing video identities.
-- Usage: Managed plugin deployment through db/liquibase/pluginController.xml.

--changeset clive:orac_chess_content_source_creator_index context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_indexes where owner='ORAC_CHESS' and index_name='CHS_CSR_CREATOR_UX'
create unique index orac_chess.chs_csr_creator_ux on orac_chess.chess_content_source (creator);
--rollback drop index orac_chess.chs_csr_creator_ux;
