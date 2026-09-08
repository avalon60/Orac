--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Sep-2026
-- Description: Destructively removes the superseded searchable-chunks view.

--changeset clive:purge_view_orac_code_knowledge_searchable_chunks_v context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_CODE' and view_name = 'KNOWLEDGE_SEARCHABLE_CHUNKS_V';
drop view orac_code.knowledge_searchable_chunks_v;
--rollback create force view orac_code.knowledge_searchable_chunks_v as select * from orac_code.knowledge_native_searchable_chunks_v;
