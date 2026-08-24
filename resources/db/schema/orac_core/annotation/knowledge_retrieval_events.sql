--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Annotates the retrieval audit entity and protected attributes.

--changeset clive:annotate_orac_core_knowledge_retrieval_events context:core labels:core stripComments:false runOnChange:true
alter table orac_core.knowledge_retrieval_events annotations (
  add classification 'SECURITY_AUDIT',
  add lifecycle 'APPEND_ONLY'
);
alter table orac_core.knowledge_retrieval_events modify username_snapshot annotations (
  add classification 'PRINCIPAL_IDENTIFIER'
);
alter table orac_core.knowledge_retrieval_events modify detail_json annotations (
  add content_policy 'IDENTIFIERS_AND_RANGES_ONLY'
);
--rollback alter table orac_core.knowledge_retrieval_events annotations (drop classification, drop lifecycle);
