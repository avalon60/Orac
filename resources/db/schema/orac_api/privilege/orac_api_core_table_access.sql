--liquibase formatted sql

-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant the api schema controlled access to ORAC_CORE tables

--changeset clive:grant_orac_core_users_to_orac_api_01 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.users to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.users from orac_api;

--changeset clive:grant_orac_core_preference_definitions_to_orac_api_02 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.preference_definitions to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.preference_definitions from orac_api;

--changeset clive:grant_orac_core_timezones_to_orac_api_03 context:core labels:core stripComments:false runOnChange:true
grant select on orac_core.timezones to orac_api with grant option;
--rollback revoke select on orac_core.timezones from orac_api;

--changeset clive:grant_orac_core_user_synonyms_to_orac_api_04 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.user_synonyms to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.user_synonyms from orac_api;

--changeset clive:grant_orac_core_user_preferences_to_orac_api_05 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.user_preferences to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.user_preferences from orac_api;

--changeset clive:grant_orac_core_messages_to_orac_api_06 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.messages to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.messages from orac_api;

--changeset clive:grant_orac_core_conversations_to_orac_api_07 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.conversations to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.conversations from orac_api;

--changeset clive:grant_orac_core_llm_registry_to_orac_api_08 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.llm_registry to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.llm_registry from orac_api;

--changeset clive:grant_orac_core_tts_voices_to_orac_api_09 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.tts_voices to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.tts_voices from orac_api;

--changeset clive:grant_orac_core_model_generation_presets_to_orac_api_10 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.model_generation_presets to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.model_generation_presets from orac_api;

--changeset clive:grant_orac_core_devices_to_orac_api_11 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.devices to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.devices from orac_api;

--changeset clive:grant_orac_core_message_embeddings_to_orac_api_12 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.message_embeddings to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.message_embeddings from orac_api;

--changeset clive:grant_orac_core_user_prompt_elements_to_orac_api_13 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.user_prompt_elements to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.user_prompt_elements from orac_api;

--changeset clive:grant_orac_core_orac_personalities_to_orac_api_14 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.orac_personalities to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.orac_personalities from orac_api;

--changeset clive:grant_orac_core_plugin_invocations_to_orac_api_15 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.plugin_invocations to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.plugin_invocations from orac_api;

--changeset clive:grant_orac_core_plugin_audit_events_to_orac_api_16 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.plugin_audit_events to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.plugin_audit_events from orac_api;

--changeset clive:grant_orac_core_plugin_db_deployments_to_orac_api_17 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.plugin_db_deployments to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.plugin_db_deployments from orac_api;

--changeset clive:grant_orac_core_plugin_apex_apps_to_orac_api_18 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.plugin_apex_apps to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.plugin_apex_apps from orac_api;

--changeset clive:grant_orac_core_plugin_registry_to_orac_api_19 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.plugin_registry to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.plugin_registry from orac_api;

--changeset clive:grant_orac_core_project_registry_to_orac_api_20 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.project_registry to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.project_registry from orac_api;
