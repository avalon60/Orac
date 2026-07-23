--liquibase formatted sql

--changeset clive:grant_orac_plugin_scope_validation_to_orac_dropbox context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: grant Drop Box only the shared canonical-scope validation bridge
grant execute on orac_plugin.knowledge_scope_validation_api to orac_dropbox;
--rollback revoke execute on orac_plugin.knowledge_scope_validation_api from orac_dropbox;
