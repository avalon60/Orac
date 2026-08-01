--liquibase formatted sql

--changeset clive:comment_knowledge_tags context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.knowledge_tags is 'Controlled non-behavioural knowledge classification tags.';
comment on table orac_core.knowledge_document_version_tags is 'Authoritative classifications assigned to knowledge document versions.';
--rollback comment on table orac_core.knowledge_document_version_tags is null; comment on table orac_core.knowledge_tags is null;
