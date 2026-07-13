--liquibase formatted sql

-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant published views to consumer schemas

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_apx_pub_01 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.preference_definitions_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.preference_definitions_v from orac_apx_pub;

--changeset clive:grant_orac_api_timezones_v_to_orac_apx_pub_02 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.timezones_v to orac_apx_pub;
--rollback revoke select on orac_api.timezones_v from orac_apx_pub;

--changeset clive:grant_orac_api_users_to_orac_apx_pub_03 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.users to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.users from orac_apx_pub;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_apx_pub_04 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_synonyms_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.user_synonyms_v from orac_apx_pub;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_apx_pub_05 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_preferences_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.user_preferences_v from orac_apx_pub;

--changeset clive:grant_orac_api_messages_v_to_orac_apx_pub_06 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.messages_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.messages_v from orac_apx_pub;

--changeset clive:grant_orac_api_conversations_v_to_orac_apx_pub_07 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.conversations_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.conversations_v from orac_apx_pub;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_apx_pub_08 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.llm_registry_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.llm_registry_v from orac_apx_pub;

--changeset clive:grant_orac_api_tts_voices_v_to_orac_apx_pub_09 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.tts_voices_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.tts_voices_v from orac_apx_pub;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_apx_pub_10 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.model_generation_presets_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.model_generation_presets_v from orac_apx_pub;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_apx_pub_11 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.orac_personalities_v to orac_apx_pub;
--rollback revoke select, insert, update, delete on orac_api.orac_personalities_v from orac_apx_pub;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_apx_pub_12 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.preference_definitions_v to orac_apx_pub;
--rollback revoke read on orac_api.preference_definitions_v from orac_apx_pub;

--changeset clive:grant_orac_api_timezones_v_to_orac_apx_pub_13 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.timezones_v to orac_apx_pub;
--rollback revoke read on orac_api.timezones_v from orac_apx_pub;

--changeset clive:grant_orac_api_users_to_orac_apx_pub_14 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.users to orac_apx_pub;
--rollback revoke read on orac_api.users from orac_apx_pub;

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

--changeset clive:grant_orac_api_tts_voices_v_to_orac_apx_pub_20 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.tts_voices_v to orac_apx_pub;
--rollback revoke read on orac_api.tts_voices_v from orac_apx_pub;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_apx_pub_21 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.model_generation_presets_v to orac_apx_pub;
--rollback revoke read on orac_api.model_generation_presets_v from orac_apx_pub;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_apx_pub_22 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.orac_personalities_v to orac_apx_pub;
--rollback revoke read on orac_api.orac_personalities_v from orac_apx_pub;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_23 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.preference_definitions_v to orac;
--rollback revoke select, insert, update, delete on orac_api.preference_definitions_v from orac;

--changeset clive:grant_orac_api_timezones_v_to_orac_24 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.timezones_v to orac;
--rollback revoke select on orac_api.timezones_v from orac;

--changeset clive:grant_orac_api_users_to_orac_25 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.users to orac;
--rollback revoke select, insert, update, delete on orac_api.users from orac;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_26 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_synonyms_v to orac;
--rollback revoke select, insert, update, delete on orac_api.user_synonyms_v from orac;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_27 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_preferences_v to orac;
--rollback revoke select, insert, update, delete on orac_api.user_preferences_v from orac;

--changeset clive:grant_orac_api_messages_v_to_orac_28 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.messages_v to orac;
--rollback revoke select, insert, update, delete on orac_api.messages_v from orac;

--changeset clive:grant_orac_api_conversations_v_to_orac_29 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.conversations_v to orac;
--rollback revoke select, insert, update, delete on orac_api.conversations_v from orac;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_30 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.llm_registry_v to orac;
--rollback revoke select, insert, update, delete on orac_api.llm_registry_v from orac;

--changeset clive:grant_orac_api_tts_voices_v_to_orac_31 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.tts_voices_v to orac;
--rollback revoke select, insert, update, delete on orac_api.tts_voices_v from orac;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_32 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.model_generation_presets_v to orac;
--rollback revoke select, insert, update, delete on orac_api.model_generation_presets_v from orac;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_33 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.orac_personalities_v to orac;
--rollback revoke select, insert, update, delete on orac_api.orac_personalities_v from orac;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_34 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.preference_definitions_v to orac;
--rollback revoke read on orac_api.preference_definitions_v from orac;

--changeset clive:grant_orac_api_timezones_v_to_orac_35 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.timezones_v to orac;
--rollback revoke read on orac_api.timezones_v from orac;

--changeset clive:grant_orac_api_users_to_orac_36 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.users to orac;
--rollback revoke read on orac_api.users from orac;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_37 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_synonyms_v to orac;
--rollback revoke read on orac_api.user_synonyms_v from orac;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_38 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_preferences_v to orac;
--rollback revoke read on orac_api.user_preferences_v from orac;

--changeset clive:grant_orac_api_messages_v_to_orac_39 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.messages_v to orac;
--rollback revoke read on orac_api.messages_v from orac;

--changeset clive:grant_orac_api_conversations_v_to_orac_40 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.conversations_v to orac;
--rollback revoke read on orac_api.conversations_v from orac;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_41 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.llm_registry_v to orac;
--rollback revoke read on orac_api.llm_registry_v from orac;

--changeset clive:grant_orac_api_tts_voices_v_to_orac_42 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.tts_voices_v to orac;
--rollback revoke read on orac_api.tts_voices_v from orac;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_43 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.model_generation_presets_v to orac;
--rollback revoke read on orac_api.model_generation_presets_v from orac;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_44 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.orac_personalities_v to orac;
--rollback revoke read on orac_api.orac_personalities_v from orac;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_code_45 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.preference_definitions_v to orac_code with grant option;
--rollback revoke select on orac_api.preference_definitions_v from orac_code;

--changeset clive:grant_orac_api_timezones_v_to_orac_code_46 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.timezones_v to orac_code with grant option;
--rollback revoke select on orac_api.timezones_v from orac_code;

--changeset clive:grant_orac_api_users_to_orac_code_47 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.users to orac_code with grant option;
--rollback revoke select on orac_api.users from orac_code;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_code_48 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.user_synonyms_v to orac_code with grant option;
--rollback revoke select on orac_api.user_synonyms_v from orac_code;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_code_49 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.user_preferences_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.user_preferences_v from orac_code;

--changeset clive:grant_orac_api_messages_v_to_orac_code_50 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.messages_v to orac_code with grant option;
--rollback revoke select on orac_api.messages_v from orac_code;

--changeset clive:grant_orac_api_conversations_v_to_orac_code_51 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.conversations_v to orac_code with grant option;
--rollback revoke select on orac_api.conversations_v from orac_code;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_code_52 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.llm_registry_v to orac_code with grant option;
--rollback revoke select on orac_api.llm_registry_v from orac_code;

--changeset clive:grant_orac_api_tts_voices_v_to_orac_code_53 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.tts_voices_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.tts_voices_v from orac_code;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_code_54 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.model_generation_presets_v to orac_code with grant option;
--rollback revoke select on orac_api.model_generation_presets_v from orac_code;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_code_55 context:core labels:core stripComments:false runOnChange:true
grant select on orac_api.orac_personalities_v to orac_code with grant option;
--rollback revoke select on orac_api.orac_personalities_v from orac_code;

--changeset clive:grant_orac_api_preference_definitions_v_to_orac_code_56 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.preference_definitions_v to orac_code with grant option;
--rollback revoke read on orac_api.preference_definitions_v from orac_code;

--changeset clive:grant_orac_api_timezones_v_to_orac_code_57 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.timezones_v to orac_code with grant option;
--rollback revoke read on orac_api.timezones_v from orac_code;

--changeset clive:grant_orac_api_users_to_orac_code_58 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.users to orac_code with grant option;
--rollback revoke read on orac_api.users from orac_code;

--changeset clive:grant_orac_api_user_synonyms_v_to_orac_code_59 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_synonyms_v to orac_code with grant option;
--rollback revoke read on orac_api.user_synonyms_v from orac_code;

--changeset clive:grant_orac_api_user_preferences_v_to_orac_code_60 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.user_preferences_v to orac_code with grant option;
--rollback revoke read on orac_api.user_preferences_v from orac_code;

--changeset clive:grant_orac_api_messages_v_to_orac_code_61 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.messages_v to orac_code with grant option;
--rollback revoke read on orac_api.messages_v from orac_code;

--changeset clive:grant_orac_api_conversations_v_to_orac_code_62 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.conversations_v to orac_code with grant option;
--rollback revoke read on orac_api.conversations_v from orac_code;

--changeset clive:grant_orac_api_llm_registry_v_to_orac_code_63 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.llm_registry_v to orac_code with grant option;
--rollback revoke read on orac_api.llm_registry_v from orac_code;

--changeset clive:grant_orac_api_tts_voices_v_to_orac_code_64 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.tts_voices_v to orac_code with grant option;
--rollback revoke read on orac_api.tts_voices_v from orac_code;

--changeset clive:grant_orac_api_model_generation_presets_v_to_orac_code_65 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.model_generation_presets_v to orac_code with grant option;
--rollback revoke read on orac_api.model_generation_presets_v from orac_code;

--changeset clive:grant_orac_api_orac_personalities_v_to_orac_code_66 context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.orac_personalities_v to orac_code with grant option;
--rollback revoke read on orac_api.orac_personalities_v from orac_code;

--changeset clive:grant_orac_api_knowledge_source_objects_v_to_orac_code_67 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_source_objects_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_source_objects_v from orac_code;

--changeset clive:grant_orac_api_knowledge_documents_v_to_orac_code_68 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_documents_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_documents_v from orac_code;

--changeset clive:grant_orac_api_knowledge_document_versions_v_to_orac_code_69 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_document_versions_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_document_versions_v from orac_code;

--changeset clive:grant_orac_api_knowledge_ingestion_requests_v_to_orac_code_70 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_ingestion_requests_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_ingestion_requests_v from orac_code;

--changeset clive:grant_orac_api_knowledge_extractions_v_to_orac_code_71 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_extractions_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_extractions_v from orac_code;

--changeset clive:grant_orac_api_knowledge_chunk_sets_v_to_orac_code_72 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_chunk_sets_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_chunk_sets_v from orac_code;

--changeset clive:grant_orac_api_knowledge_chunks_v_to_orac_code_73 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_chunks_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_chunks_v from orac_code;

--changeset clive:grant_orac_api_knowledge_embedding_models_v_to_orac_code_74 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_embedding_models_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_embedding_models_v from orac_code;

--changeset clive:grant_orac_api_knowledge_chunk_embeddings_v_to_orac_code_75 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_chunk_embeddings_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_chunk_embeddings_v from orac_code;

--changeset clive:grant_orac_api_knowledge_ingestion_events_v_to_orac_code_76 context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_api.knowledge_ingestion_events_v to orac_code with grant option;
--rollback revoke select, insert, update, delete on orac_api.knowledge_ingestion_events_v from orac_code;
