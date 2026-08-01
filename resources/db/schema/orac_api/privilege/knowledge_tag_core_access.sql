--liquibase formatted sql

--changeset clive:grant_knowledge_tags_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_tags to orac_api with grant option;
grant select, insert, update, delete on orac_core.knowledge_document_version_tags to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_document_version_tags from orac_api; revoke select, insert, update, delete on orac_core.knowledge_tags from orac_api;
