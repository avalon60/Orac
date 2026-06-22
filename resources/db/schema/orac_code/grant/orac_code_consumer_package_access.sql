--liquibase formatted sql

-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant ORAC_CODE business packages to consumer schemas

--changeset clive:grant_orac_code_orac_prefs_seed_to_orac_apx_pub_01 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.orac_prefs_seed to orac_apx_pub;
--rollback revoke execute on orac_code.orac_prefs_seed from orac_apx_pub;

--changeset clive:grant_orac_code_orac_prefs_seed_to_orac_02 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.orac_prefs_seed to orac;
--rollback revoke execute on orac_code.orac_prefs_seed from orac;

--changeset clive:grant_orac_code_preference_lov_api_to_orac_apx_pub_03 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.preference_lov_api to orac_apx_pub;
--rollback revoke execute on orac_code.preference_lov_api from orac_apx_pub;

--changeset clive:grant_orac_code_preference_lov_api_to_orac_04 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.preference_lov_api to orac;
--rollback revoke execute on orac_code.preference_lov_api from orac;

--changeset clive:grant_orac_code_orac_personalities_api_to_orac_apx_pub_05 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.orac_personalities_api to orac_apx_pub;
--rollback revoke execute on orac_code.orac_personalities_api from orac_apx_pub;

--changeset clive:grant_orac_code_orac_personalities_api_to_orac_06 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.orac_personalities_api to orac;
--rollback revoke execute on orac_code.orac_personalities_api from orac;

--changeset clive:grant_orac_code_user_preferences_api_to_orac_apx_pub_07 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.user_preferences_api to orac_apx_pub;
--rollback revoke execute on orac_code.user_preferences_api from orac_apx_pub;

--changeset clive:grant_orac_code_user_preferences_api_to_orac_08 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.user_preferences_api to orac;
--rollback revoke execute on orac_code.user_preferences_api from orac;

--changeset clive:grant_orac_code_plugin_audit_api_to_orac_09 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.plugin_audit_api to orac;
--rollback revoke execute on orac_code.plugin_audit_api from orac;

--changeset clive:grant_orac_code_plugin_db_deployment_api_to_orac_10 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.plugin_db_deployment_api to orac;
--rollback revoke execute on orac_code.plugin_db_deployment_api from orac;

--changeset clive:grant_orac_code_plugin_apex_app_registry_api_to_orac_11 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.plugin_apex_app_registry_api to orac;
--rollback revoke execute on orac_code.plugin_apex_app_registry_api from orac;

--changeset clive:grant_orac_code_plugin_registry_api_to_orac_12 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_code.plugin_registry_api to orac;
--rollback revoke execute on orac_code.plugin_registry_api from orac;
