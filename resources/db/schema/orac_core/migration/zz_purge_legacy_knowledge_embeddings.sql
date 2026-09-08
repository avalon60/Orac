--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Sep-2026
-- Description: Destructively removes superseded JSON/CLOB knowledge embeddings.

--changeset clive:purge_table_orac_core_knowledge_chunk_embeddings context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'KNOWLEDGE_CHUNK_EMBEDDINGS';
drop table orac_core.knowledge_chunk_embeddings cascade constraints purge;
