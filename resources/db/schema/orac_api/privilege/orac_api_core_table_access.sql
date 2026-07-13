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

--changeset clive:grant_orac_core_orac_search_queries_to_orac_api_21 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.orac_search_queries to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.orac_search_queries from orac_api;

--changeset clive:grant_orac_core_orac_search_results_to_orac_api_22 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.orac_search_results to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.orac_search_results from orac_api;

--changeset clive:grant_orac_core_orac_fetched_sources_to_orac_api_23 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.orac_fetched_sources to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.orac_fetched_sources from orac_api;

--changeset clive:grant_orac_core_knowledge_source_objects_to_orac_api_24 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_source_objects to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_source_objects from orac_api;

--changeset clive:grant_orac_core_knowledge_documents_to_orac_api_25 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_documents to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_documents from orac_api;

--changeset clive:grant_orac_core_knowledge_document_versions_to_orac_api_26 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_document_versions to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_document_versions from orac_api;

--changeset clive:grant_orac_core_knowledge_ingestion_requests_to_orac_api_27 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_ingestion_requests to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_ingestion_requests from orac_api;

--changeset clive:grant_orac_core_knowledge_extractions_to_orac_api_28 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_extractions to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_extractions from orac_api;

--changeset clive:grant_orac_core_knowledge_chunk_sets_to_orac_api_29 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_chunk_sets to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_chunk_sets from orac_api;

--changeset clive:grant_orac_core_knowledge_chunks_to_orac_api_30 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_chunks to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_chunks from orac_api;

--changeset clive:grant_orac_core_knowledge_embedding_models_to_orac_api_31 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_embedding_models to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_embedding_models from orac_api;

--changeset clive:grant_orac_core_knowledge_chunk_embeddings_to_orac_api_32 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_chunk_embeddings to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_chunk_embeddings from orac_api;

--changeset clive:grant_orac_core_knowledge_ingestion_events_to_orac_api_33 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.knowledge_ingestion_events to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.knowledge_ingestion_events from orac_api;
