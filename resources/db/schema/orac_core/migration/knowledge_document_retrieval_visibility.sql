--liquibase formatted sql
-- Author: clive
-- Date: 11-Oct-2026
-- Description: Allows an existing knowledge document to be withdrawn from retrieval.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:add_kn_doc_retrieval_enabled_yn context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner = 'ORAC_CORE' and table_name = 'KNOWLEDGE_DOCUMENTS' and column_name = 'RETRIEVAL_ENABLED_YN';
alter table orac_core.knowledge_documents add (
  retrieval_enabled_yn varchar2(1 char) default 'Y' not null
);
--rollback alter table orac_core.knowledge_documents drop column retrieval_enabled_yn;

--changeset clive:add_kn_doc_retrieval_enabled_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_constraints where owner = 'ORAC_CORE' and table_name = 'KNOWLEDGE_DOCUMENTS' and constraint_name = 'KN_DOC_RETRIEVAL_ENABLED_CK';
alter table orac_core.knowledge_documents add constraint kn_doc_retrieval_enabled_ck
  check (retrieval_enabled_yn in ('Y', 'N'));
--rollback alter table orac_core.knowledge_documents drop constraint kn_doc_retrieval_enabled_ck;
