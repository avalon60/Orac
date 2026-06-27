--liquibase formatted sql

-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant ORAC_CODE reporting and business views to consumer schemas

--changeset clive:grant_orac_code_messages_per_day_v_to_orac_apx_pub_01 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.messages_per_day_v to orac_apx_pub;
--rollback revoke select on orac_code.messages_per_day_v from orac_apx_pub;

--changeset clive:grant_orac_code_llm_usage_breakdown_v_to_orac_apx_pub_02 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.llm_usage_breakdown_v to orac_apx_pub;
--rollback revoke select on orac_code.llm_usage_breakdown_v from orac_apx_pub;

--changeset clive:grant_orac_code_llm_registry_probe_v_to_orac_apx_pub_03 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.llm_registry_probe_v to orac_apx_pub;
--rollback revoke select on orac_code.llm_registry_probe_v from orac_apx_pub;

--changeset clive:grant_orac_code_token_usage_trend_v_to_orac_apx_pub_04 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.token_usage_trend_v to orac_apx_pub;
--rollback revoke select on orac_code.token_usage_trend_v from orac_apx_pub;

--changeset clive:grant_orac_code_message_role_breakdown_v_to_orac_apx_pub_05 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.message_role_breakdown_v to orac_apx_pub;
--rollback revoke select on orac_code.message_role_breakdown_v from orac_apx_pub;

--changeset clive:grant_orac_code_user_preferences_v_to_orac_apx_pub_06 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_code.user_preferences_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_code.user_preferences_v from orac_apx_pub;

--changeset clive:grant_orac_code_user_preferences_v_to_orac_apx_pub_07 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.user_preferences_v to orac_apx_pub;
--rollback revoke read on orac_code.user_preferences_v from orac_apx_pub;

--changeset clive:grant_orac_code_user_preferences_display_v_to_orac_apx_pub_08 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.user_preferences_display_v to orac_apx_pub;
--rollback revoke select on orac_code.user_preferences_display_v from orac_apx_pub;

--changeset clive:grant_orac_code_plugin_apex_app_menu_v_to_orac_apx_pub_09 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_apex_app_menu_v to orac_apx_pub;
--rollback revoke read on orac_code.plugin_apex_app_menu_v from orac_apx_pub;

--changeset clive:grant_orac_code_plugin_apex_app_menu_visible_v_to_orac_apx_pub_21 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_apex_app_menu_visible_v to orac_apx_pub;
--rollback revoke read on orac_code.plugin_apex_app_menu_visible_v from orac_apx_pub;

--changeset clive:grant_orac_code_plugin_apex_apps_v_to_orac_apx_pub_22 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_apex_apps_v to orac_apx_pub;
--rollback revoke read on orac_code.plugin_apex_apps_v from orac_apx_pub;

--changeset clive:grant_orac_code_plugin_lov_v_to_orac_apx_pub_23 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_lov_v to orac_apx_pub;
--rollback revoke read on orac_code.plugin_lov_v from orac_apx_pub;

--changeset clive:grant_orac_code_messages_per_day_v_to_orac_10 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.messages_per_day_v to orac;
--rollback revoke select on orac_code.messages_per_day_v from orac;

--changeset clive:grant_orac_code_llm_usage_breakdown_v_to_orac_11 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.llm_usage_breakdown_v to orac;
--rollback revoke select on orac_code.llm_usage_breakdown_v from orac;

--changeset clive:grant_orac_code_llm_registry_probe_v_to_orac_12 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.llm_registry_probe_v to orac;
--rollback revoke select on orac_code.llm_registry_probe_v from orac;

--changeset clive:grant_orac_code_token_usage_trend_v_to_orac_13 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.token_usage_trend_v to orac;
--rollback revoke select on orac_code.token_usage_trend_v from orac;

--changeset clive:grant_orac_code_message_role_breakdown_v_to_orac_14 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.message_role_breakdown_v to orac;
--rollback revoke select on orac_code.message_role_breakdown_v from orac;

--changeset clive:grant_orac_code_user_preferences_v_to_orac_15 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_code.user_preferences_v to orac;
--rollback revoke select, insert, update, delete on orac_code.user_preferences_v from orac;

--changeset clive:grant_orac_code_user_preferences_v_to_orac_16 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.user_preferences_v to orac;
--rollback revoke read on orac_code.user_preferences_v from orac;

--changeset clive:grant_orac_code_user_preferences_display_v_to_orac_17 context:core labels:core stripComments:false runOnChange:true
grant select on orac_code.user_preferences_display_v to orac;
--rollback revoke select on orac_code.user_preferences_display_v from orac;

--changeset clive:grant_orac_code_plugin_apex_apps_v_to_orac_18 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_apex_apps_v to orac;
--rollback revoke read on orac_code.plugin_apex_apps_v from orac;

--changeset clive:grant_orac_code_plugin_apex_app_menu_v_to_orac_19 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_apex_app_menu_v to orac;
--rollback revoke read on orac_code.plugin_apex_app_menu_v from orac;

--changeset clive:grant_orac_code_plugin_registry_v_to_orac_20 context:core labels:core stripComments:false runOnChange:true
grant read on orac_code.plugin_registry_v to orac;
--rollback revoke read on orac_code.plugin_registry_v from orac;
