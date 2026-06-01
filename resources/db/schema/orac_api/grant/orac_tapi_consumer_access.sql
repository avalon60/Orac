-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant the existing orac_tapi view and TAPI surface to consumer schemas

grant select, insert, update, delete on orac_api.preference_definitions_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.users_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.user_synonyms_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.user_preferences_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.messages_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.conversations_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.llm_registry_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.model_generation_presets_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.devices_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.message_embeddings_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.orac_personalities_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.user_prompt_elements_v to orac_apx_pub;

grant read on orac_api.preference_definitions_v to orac_apx_pub;
grant read on orac_api.users_v to orac_apx_pub;
grant read on orac_api.user_synonyms_v to orac_apx_pub;
grant read on orac_api.user_preferences_v to orac_apx_pub;
grant read on orac_api.messages_v to orac_apx_pub;
grant read on orac_api.conversations_v to orac_apx_pub;
grant read on orac_api.llm_registry_v to orac_apx_pub;
grant read on orac_api.model_generation_presets_v to orac_apx_pub;
grant read on orac_api.devices_v to orac_apx_pub;
grant read on orac_api.message_embeddings_v to orac_apx_pub;
grant read on orac_api.orac_personalities_v to orac_apx_pub;
grant read on orac_api.user_prompt_elements_v to orac_apx_pub;

grant select, insert, update, delete on orac_api.preference_definitions_v to orac;
grant select, insert, update, delete on orac_api.users_v to orac;
grant select, insert, update, delete on orac_api.user_synonyms_v to orac;
grant select, insert, update, delete on orac_api.user_preferences_v to orac;
grant select, insert, update, delete on orac_api.messages_v to orac;
grant select, insert, update, delete on orac_api.conversations_v to orac;
grant select, insert, update, delete on orac_api.llm_registry_v to orac;
grant select, insert, update, delete on orac_api.model_generation_presets_v to orac;
grant select, insert, update, delete on orac_api.devices_v to orac;
grant select, insert, update, delete on orac_api.message_embeddings_v to orac;
grant select, insert, update, delete on orac_api.orac_personalities_v to orac;
grant select, insert, update, delete on orac_api.user_prompt_elements_v to orac;

grant read on orac_api.preference_definitions_v to orac;
grant read on orac_api.users_v to orac;
grant read on orac_api.user_synonyms_v to orac;
grant read on orac_api.user_preferences_v to orac;
grant read on orac_api.messages_v to orac;
grant read on orac_api.conversations_v to orac;
grant read on orac_api.llm_registry_v to orac;
grant read on orac_api.model_generation_presets_v to orac;
grant read on orac_api.devices_v to orac;
grant read on orac_api.message_embeddings_v to orac;
grant read on orac_api.orac_personalities_v to orac;
grant read on orac_api.user_prompt_elements_v to orac;

grant select on orac_api.preference_definitions_v to orac_code with grant option;
grant select on orac_api.users_v to orac_code with grant option;
grant select on orac_api.user_synonyms_v to orac_code with grant option;
grant select, insert, update, delete on orac_api.user_preferences_v to orac_code with grant option;
grant select on orac_api.messages_v to orac_code with grant option;
grant select on orac_api.conversations_v to orac_code with grant option;
grant select on orac_api.llm_registry_v to orac_code with grant option;
grant select on orac_api.model_generation_presets_v to orac_code with grant option;
grant select on orac_api.devices_v to orac_code with grant option;
grant select on orac_api.message_embeddings_v to orac_code with grant option;
grant select on orac_api.orac_personalities_v to orac_code with grant option;
grant select on orac_api.user_prompt_elements_v to orac_code with grant option;
grant select on orac_api.plugin_invocations_v to orac_code with grant option;
grant select on orac_api.plugin_audit_events_v to orac_code with grant option;

grant read on orac_api.preference_definitions_v to orac_code with grant option;
grant read on orac_api.users_v to orac_code with grant option;
grant read on orac_api.user_synonyms_v to orac_code with grant option;
grant read on orac_api.user_preferences_v to orac_code with grant option;
grant read on orac_api.messages_v to orac_code with grant option;
grant read on orac_api.conversations_v to orac_code with grant option;
grant read on orac_api.llm_registry_v to orac_code with grant option;
grant read on orac_api.model_generation_presets_v to orac_code with grant option;
grant read on orac_api.devices_v to orac_code with grant option;
grant read on orac_api.message_embeddings_v to orac_code with grant option;
grant read on orac_api.orac_personalities_v to orac_code with grant option;
grant read on orac_api.user_prompt_elements_v to orac_code with grant option;
grant read on orac_api.plugin_invocations_v to orac_code with grant option;
grant read on orac_api.plugin_audit_events_v to orac_code with grant option;

grant execute on orac_api.preference_definitions_tapi to orac_code;
grant execute on orac_api.users_tapi to orac_code;
grant execute on orac_api.user_synonyms_tapi to orac_code;
grant execute on orac_api.user_preferences_tapi to orac_code;
grant execute on orac_api.messages_tapi to orac_code;
grant execute on orac_api.conversations_tapi to orac_code;
grant execute on orac_api.llm_registry_tapi to orac_code;
grant execute on orac_api.devices_tapi to orac_code;
grant execute on orac_api.message_embeddings_tapi to orac_code;
grant execute on orac_api.orac_personalities_tapi to orac_code;
grant execute on orac_api.user_prompt_elements_tapi to orac_code;
grant execute on orac_api.plugin_invocations_tapi to orac_code;
grant execute on orac_api.plugin_audit_events_tapi to orac_code;
