--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Sep-2026
-- Description: Destructively removes the superseded legacy embedding API view.

--changeset clive:purge_view_orac_api_knowledge_chunk_embeddings_v context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_views where owner = 'ORAC_API' and view_name = 'KNOWLEDGE_CHUNK_EMBEDDINGS_V';
drop view orac_api.knowledge_chunk_embeddings_v;
--rollback create force view orac_api.knowledge_chunk_embeddings_v as select * from orac_core.knowledge_chunk_embeddings;
