--liquibase formatted sql

--changeset clive:grant_knowledge_tag_lov_to_apex context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.knowledge_tag_lov_v to orac_apx_pub;
grant read on orac_code.knowledge_tag_lov_v to orac_plugin;
--rollback revoke read on orac_code.knowledge_tag_lov_v from orac_plugin; revoke read on orac_code.knowledge_tag_lov_v from orac_apx_pub;
