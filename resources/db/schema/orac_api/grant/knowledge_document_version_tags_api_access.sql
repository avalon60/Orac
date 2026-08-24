--liquibase formatted sql

--changeset clive:grant_read_kn_docvtag_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.knowledge_document_version_tags_v to orac_code with grant option;

--rollback revoke read on orac_api.knowledge_document_version_tags_v from orac_code;

--changeset clive:grant_execute_kn_docvtag_tapi_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.knowledge_document_version_tags_tapi to orac_code;

--rollback revoke execute on orac_api.knowledge_document_version_tags_tapi from orac_code;
