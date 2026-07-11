--liquibase formatted sql

-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant the existing orac_tapi view and TAPI surface to consumer schemas

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_apx_pub_01 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.preference_definitions_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.preference_definitions_v from orac_apx_pub;

--changeset clive:grant_orac_api_users_v_to_orac_apx_pub_02 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.users_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.users_v from orac_apx_pub;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_apx_pub_03 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_synonyms_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.user_synonyms_v from orac_apx_pub;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_apx_pub_04 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_preferences_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.user_preferences_v from orac_apx_pub;

--changeset clive:grant_orac_api_messages_v_to_orac_apx_pub_05 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.messages_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.messages_v from orac_apx_pub;

--changeset clive:grant_orac_api_conversations_v_to_orac_apx_pub_06 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.conversations_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.conversations_v from orac_apx_pub;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_apx_pub_07 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.llm_registry_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.llm_registry_v from orac_apx_pub;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_apx_pub_08 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.model_generation_presets_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.model_generation_presets_v from orac_apx_pub;

--changeset clive:grant_orac_api_devices_v_to_orac_apx_pub_09 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.devices_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.devices_v from orac_apx_pub;

--changeset clive:grant_orac_api_message_embeddings_v_to_orac_apx_pub_10 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.message_embeddings_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.message_embeddings_v from orac_apx_pub;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_apx_pub_11 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.orac_personalities_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.orac_personalities_v from orac_apx_pub;

--changeset clive:grant_orac_api_user_prompt_elements_v_to_orac_apx_pub_12 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_prompt_elements_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.user_prompt_elements_v from orac_apx_pub;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_apx_pub_13 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.preference_definitions_v to orac_apx_pub;
--rollback revoke read on orac_api.preference_definitions_v from orac_apx_pub;

--changeset clive:grant_orac_api_users_v_to_orac_apx_pub_14 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.users_v to orac_apx_pub;
--rollback revoke read on orac_api.users_v from orac_apx_pub;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_apx_pub_15 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_synonyms_v to orac_apx_pub;
--rollback revoke read on orac_api.user_synonyms_v from orac_apx_pub;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_apx_pub_16 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_preferences_v to orac_apx_pub;
--rollback revoke read on orac_api.user_preferences_v from orac_apx_pub;

--changeset clive:grant_orac_api_messages_v_to_orac_apx_pub_17 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.messages_v to orac_apx_pub;
--rollback revoke read on orac_api.messages_v from orac_apx_pub;

--changeset clive:grant_orac_api_conversations_v_to_orac_apx_pub_18 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.conversations_v to orac_apx_pub;
--rollback revoke read on orac_api.conversations_v from orac_apx_pub;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_apx_pub_19 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.llm_registry_v to orac_apx_pub;
--rollback revoke read on orac_api.llm_registry_v from orac_apx_pub;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_apx_pub_20 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.model_generation_presets_v to orac_apx_pub;
--rollback revoke read on orac_api.model_generation_presets_v from orac_apx_pub;

--changeset clive:grant_orac_api_devices_v_to_orac_apx_pub_21 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.devices_v to orac_apx_pub;
--rollback revoke read on orac_api.devices_v from orac_apx_pub;

--changeset clive:grant_orac_api_message_embeddings_v_to_orac_apx_pub_22 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.message_embeddings_v to orac_apx_pub;
--rollback revoke read on orac_api.message_embeddings_v from orac_apx_pub;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_apx_pub_23 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.orac_personalities_v to orac_apx_pub;
--rollback revoke read on orac_api.orac_personalities_v from orac_apx_pub;

--changeset clive:grant_orac_api_user_prompt_elements_v_to_orac_apx_pub_24 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_prompt_elements_v to orac_apx_pub;
--rollback revoke read on orac_api.user_prompt_elements_v from orac_apx_pub;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_25 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.preference_definitions_v to orac;
--rollback revoke select, insert, update, delete on orac_api.preference_definitions_v from orac;

--changeset clive:grant_orac_api_users_v_to_orac_26 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.users_v to orac;
--rollback revoke select, insert, update, delete on orac_api.users_v from orac;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_27 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_synonyms_v to orac;
--rollback revoke select, insert, update, delete on orac_api.user_synonyms_v from orac;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_28 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_preferences_v to orac;
--rollback revoke select, insert, update, delete on orac_api.user_preferences_v from orac;

--changeset clive:grant_orac_api_messages_v_to_orac_29 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.messages_v to orac;
--rollback revoke select, insert, update, delete on orac_api.messages_v from orac;

--changeset clive:grant_orac_api_conversations_v_to_orac_30 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.conversations_v to orac;
--rollback revoke select, insert, update, delete on orac_api.conversations_v from orac;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_31 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.llm_registry_v to orac;
--rollback revoke select, insert, update, delete on orac_api.llm_registry_v from orac;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_32 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.model_generation_presets_v to orac;
--rollback revoke select, insert, update, delete on orac_api.model_generation_presets_v from orac;

--changeset clive:grant_orac_api_devices_v_to_orac_33 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.devices_v to orac;
--rollback revoke select, insert, update, delete on orac_api.devices_v from orac;

--changeset clive:grant_orac_api_message_embeddings_v_to_orac_34 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.message_embeddings_v to orac;
--rollback revoke select, insert, update, delete on orac_api.message_embeddings_v from orac;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_35 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.orac_personalities_v to orac;
--rollback revoke select, insert, update, delete on orac_api.orac_personalities_v from orac;

--changeset clive:grant_orac_api_user_prompt_elements_v_to_orac_36 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_prompt_elements_v to orac;
--rollback revoke select, insert, update, delete on orac_api.user_prompt_elements_v from orac;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_37 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.preference_definitions_v to orac;
--rollback revoke read on orac_api.preference_definitions_v from orac;

--changeset clive:grant_orac_api_users_v_to_orac_38 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.users_v to orac;
--rollback revoke read on orac_api.users_v from orac;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_39 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_synonyms_v to orac;
--rollback revoke read on orac_api.user_synonyms_v from orac;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_40 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_preferences_v to orac;
--rollback revoke read on orac_api.user_preferences_v from orac;

--changeset clive:grant_orac_api_messages_v_to_orac_41 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.messages_v to orac;
--rollback revoke read on orac_api.messages_v from orac;

--changeset clive:grant_orac_api_conversations_v_to_orac_42 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.conversations_v to orac;
--rollback revoke read on orac_api.conversations_v from orac;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_43 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.llm_registry_v to orac;
--rollback revoke read on orac_api.llm_registry_v from orac;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_44 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.model_generation_presets_v to orac;
--rollback revoke read on orac_api.model_generation_presets_v from orac;

--changeset clive:grant_orac_api_devices_v_to_orac_45 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.devices_v to orac;
--rollback revoke read on orac_api.devices_v from orac;

--changeset clive:grant_orac_api_message_embeddings_v_to_orac_46 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.message_embeddings_v to orac;
--rollback revoke read on orac_api.message_embeddings_v from orac;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_47 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.orac_personalities_v to orac;
--rollback revoke read on orac_api.orac_personalities_v from orac;

--changeset clive:grant_orac_api_user_prompt_elements_v_to_orac_48 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_prompt_elements_v to orac;
--rollback revoke read on orac_api.user_prompt_elements_v from orac;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_code_49 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.preference_definitions_v to orac_code with grant option;
--rollback revoke select on orac_api.preference_definitions_v from orac_code;

--changeset clive:grant_orac_api_users_v_to_orac_code_50 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.users_v to orac_code with grant option;
--rollback revoke select on orac_api.users_v from orac_code;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_code_51 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.user_synonyms_v to orac_code with grant option;
--rollback revoke select on orac_api.user_synonyms_v from orac_code;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_code_52 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_preferences_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.user_preferences_v from orac_code;

--changeset clive:grant_orac_api_messages_v_to_orac_code_53 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.messages_v to orac_code with grant option;
--rollback revoke select on orac_api.messages_v from orac_code;

--changeset clive:grant_orac_api_conversations_v_to_orac_code_54 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.conversations_v to orac_code with grant option;
--rollback revoke select on orac_api.conversations_v from orac_code;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_code_55 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.llm_registry_v to orac_code with grant option;
--rollback revoke select on orac_api.llm_registry_v from orac_code;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_code_56 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.model_generation_presets_v to orac_code with grant option;
--rollback revoke select on orac_api.model_generation_presets_v from orac_code;

--changeset clive:grant_orac_api_devices_v_to_orac_code_57 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.devices_v to orac_code with grant option;
--rollback revoke select on orac_api.devices_v from orac_code;

--changeset clive:grant_orac_api_message_embeddings_v_to_orac_code_58 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.message_embeddings_v to orac_code with grant option;
--rollback revoke select on orac_api.message_embeddings_v from orac_code;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_code_59 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.orac_personalities_v to orac_code with grant option;
--rollback revoke select on orac_api.orac_personalities_v from orac_code;

--changeset clive:grant_orac_api_user_prompt_elements_v_to_orac_code_60 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.user_prompt_elements_v to orac_code with grant option;
--rollback revoke select on orac_api.user_prompt_elements_v from orac_code;

--changeset clive:grant_orac_api_plugin_invocations_v_to_orac_code_61 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.plugin_invocations_v to orac_code with grant option;
--rollback revoke select on orac_api.plugin_invocations_v from orac_code;

--changeset clive:grant_orac_api_plugin_audit_events_v_to_orac_code_62 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.plugin_audit_events_v to orac_code with grant option;
--rollback revoke select on orac_api.plugin_audit_events_v from orac_code;

--changeset clive:grant_orac_api_plugin_db_deployments_v_to_orac_code_63 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.plugin_db_deployments_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.plugin_db_deployments_v from orac_code;

--changeset clive:grant_orac_api_plugin_apex_apps_v_to_orac_code_64 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.plugin_apex_apps_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.plugin_apex_apps_v from orac_code;

--changeset clive:grant_orac_api_plugin_registry_v_to_orac_code_65 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.plugin_registry_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.plugin_registry_v from orac_code;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_code_66 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.preference_definitions_v to orac_code with grant option;
--rollback revoke read on orac_api.preference_definitions_v from orac_code;

--changeset clive:grant_orac_api_users_v_to_orac_code_67 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.users_v to orac_code with grant option;
--rollback revoke read on orac_api.users_v from orac_code;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_code_68 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_synonyms_v to orac_code with grant option;
--rollback revoke read on orac_api.user_synonyms_v from orac_code;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_code_69 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_preferences_v to orac_code with grant option;
--rollback revoke read on orac_api.user_preferences_v from orac_code;

--changeset clive:grant_orac_api_messages_v_to_orac_code_70 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.messages_v to orac_code with grant option;
--rollback revoke read on orac_api.messages_v from orac_code;

--changeset clive:grant_orac_api_conversations_v_to_orac_code_71 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.conversations_v to orac_code with grant option;
--rollback revoke read on orac_api.conversations_v from orac_code;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_code_72 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.llm_registry_v to orac_code with grant option;
--rollback revoke read on orac_api.llm_registry_v from orac_code;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_code_73 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.model_generation_presets_v to orac_code with grant option;
--rollback revoke read on orac_api.model_generation_presets_v from orac_code;

--changeset clive:grant_orac_api_devices_v_to_orac_code_74 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.devices_v to orac_code with grant option;
--rollback revoke read on orac_api.devices_v from orac_code;

--changeset clive:grant_orac_api_message_embeddings_v_to_orac_code_75 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.message_embeddings_v to orac_code with grant option;
--rollback revoke read on orac_api.message_embeddings_v from orac_code;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_code_76 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.orac_personalities_v to orac_code with grant option;
--rollback revoke read on orac_api.orac_personalities_v from orac_code;

--changeset clive:grant_orac_api_user_prompt_elements_v_to_orac_code_77 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_prompt_elements_v to orac_code with grant option;
--rollback revoke read on orac_api.user_prompt_elements_v from orac_code;

--changeset clive:grant_orac_api_plugin_invocations_v_to_orac_code_78 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.plugin_invocations_v to orac_code with grant option;
--rollback revoke read on orac_api.plugin_invocations_v from orac_code;

--changeset clive:grant_orac_api_plugin_audit_events_v_to_orac_code_79 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.plugin_audit_events_v to orac_code with grant option;
--rollback revoke read on orac_api.plugin_audit_events_v from orac_code;

--changeset clive:grant_orac_api_plugin_db_deployments_v_to_orac_code_80 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.plugin_db_deployments_v to orac_code with grant option;
--rollback revoke read on orac_api.plugin_db_deployments_v from orac_code;

--changeset clive:grant_orac_api_plugin_apex_apps_v_to_orac_code_81 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.plugin_apex_apps_v to orac_code with grant option;
--rollback revoke read on orac_api.plugin_apex_apps_v from orac_code;

--changeset clive:grant_orac_api_plugin_registry_v_to_orac_code_82 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.plugin_registry_v to orac_code with grant option;
--rollback revoke read on orac_api.plugin_registry_v from orac_code;

--changeset clive:grant_orac_api_project_registry_v_to_orac_code_dml context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.project_registry_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.project_registry_v from orac_code;

--changeset clive:grant_orac_api_project_registry_v_to_orac_code_read context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.project_registry_v to orac_code with grant option;
--rollback revoke read on orac_api.project_registry_v from orac_code;

--changeset clive:grant_orac_api_preference_definitions_tapi_to_orac_code_83 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.preference_definitions_tapi to orac_code;
--rollback revoke execute on orac_api.preference_definitions_tapi from orac_code;

--changeset clive:grant_orac_api_users_tapi_to_orac_code_84 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.users_tapi to orac_code;
--rollback revoke execute on orac_api.users_tapi from orac_code;

--changeset clive:grant_orac_api_user_synonyms_tapi_to_orac_code_85 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.user_synonyms_tapi to orac_code;
--rollback revoke execute on orac_api.user_synonyms_tapi from orac_code;

--changeset clive:grant_orac_api_user_preferences_tapi_to_orac_code_86 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.user_preferences_tapi to orac_code;
--rollback revoke execute on orac_api.user_preferences_tapi from orac_code;

--changeset clive:grant_orac_api_messages_tapi_to_orac_code_87 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.messages_tapi to orac_code;
--rollback revoke execute on orac_api.messages_tapi from orac_code;

--changeset clive:grant_orac_api_conversations_tapi_to_orac_code_88 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.conversations_tapi to orac_code;
--rollback revoke execute on orac_api.conversations_tapi from orac_code;

--changeset clive:grant_orac_api_llm_registry_tapi_to_orac_code_89 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.llm_registry_tapi to orac_code;
--rollback revoke execute on orac_api.llm_registry_tapi from orac_code;

--changeset clive:grant_orac_api_devices_tapi_to_orac_code_90 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.devices_tapi to orac_code;
--rollback revoke execute on orac_api.devices_tapi from orac_code;

--changeset clive:grant_orac_api_message_embeddings_tapi_to_orac_code_91 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.message_embeddings_tapi to orac_code;
--rollback revoke execute on orac_api.message_embeddings_tapi from orac_code;

--changeset clive:grant_orac_api_orac_personalities_tapi_to_orac_code_92 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.orac_personalities_tapi to orac_code;
--rollback revoke execute on orac_api.orac_personalities_tapi from orac_code;

--changeset clive:grant_orac_api_user_prompt_elements_tapi_to_orac_code_93 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.user_prompt_elements_tapi to orac_code;
--rollback revoke execute on orac_api.user_prompt_elements_tapi from orac_code;

--changeset clive:grant_orac_api_plugin_invocations_tapi_to_orac_code_94 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.plugin_invocations_tapi to orac_code;
--rollback revoke execute on orac_api.plugin_invocations_tapi from orac_code;

--changeset clive:grant_orac_api_plugin_audit_events_tapi_to_orac_code_95 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.plugin_audit_events_tapi to orac_code;
--rollback revoke execute on orac_api.plugin_audit_events_tapi from orac_code;

--changeset clive:grant_orac_api_plugin_db_deployments_tapi_to_orac_code_96 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.plugin_db_deployments_tapi to orac_code;
--rollback revoke execute on orac_api.plugin_db_deployments_tapi from orac_code;

--changeset clive:grant_orac_api_plugin_apex_apps_tapi_to_orac_code_97 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.plugin_apex_apps_tapi to orac_code;
--rollback revoke execute on orac_api.plugin_apex_apps_tapi from orac_code;

--changeset clive:grant_orac_api_plugin_registry_tapi_to_orac_code_98 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.plugin_registry_tapi to orac_code;
--rollback revoke execute on orac_api.plugin_registry_tapi from orac_code;

--changeset clive:grant_orac_api_project_registry_tapi_to_orac_code_99 context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.project_registry_tapi to orac_code;
--rollback revoke execute on orac_api.project_registry_tapi from orac_code;
