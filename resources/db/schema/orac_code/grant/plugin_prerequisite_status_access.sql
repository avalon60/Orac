--liquibase formatted sql

--changeset clive:grant_plugin_prerequisite_status_to_apex context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.plugin_prerequisite_status_v to orac_apx_pub;
--rollback revoke select on orac_code.plugin_prerequisite_status_v from orac_apx_pub;
