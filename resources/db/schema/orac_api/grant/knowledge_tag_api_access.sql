--liquibase formatted sql

--changeset clive:grant_knowledge_tag_views_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.knowledge_tags_v to orac_code with grant option;
grant select on orac_api.knowledge_document_version_tags_v to orac_code with grant option;
grant execute on orac_api.knowledge_tags_tapi to orac_code;
grant execute on orac_api.knowledge_document_version_tags_tapi to orac_code;
--rollback revoke execute on orac_api.knowledge_document_version_tags_tapi from orac_code; revoke execute on orac_api.knowledge_tags_tapi from orac_code; revoke select on orac_api.knowledge_document_version_tags_v from orac_code; revoke select on orac_api.knowledge_tags_v from orac_code;
