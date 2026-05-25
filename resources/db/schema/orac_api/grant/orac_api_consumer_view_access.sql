-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant published views to consumer schemas

grant select, insert, update, delete on orac_api.preference_definitions_v to orac_apx_pub;
grant select on orac_api.timezones_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.users to orac_apx_pub;
grant select, insert, update, delete on orac_api.user_synonyms_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.user_preferences_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.messages_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.conversations_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.llm_registry_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.tts_voices_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.model_generation_presets_v to orac_apx_pub;
grant select, insert, update, delete on orac_api.orac_personalities_v to orac_apx_pub;

grant read on orac_api.preference_definitions_v to orac_apx_pub;
grant read on orac_api.timezones_v to orac_apx_pub;
grant read on orac_api.users to orac_apx_pub;
grant read on orac_api.user_synonyms_v to orac_apx_pub;
grant read on orac_api.user_preferences_v to orac_apx_pub;
grant read on orac_api.messages_v to orac_apx_pub;
grant read on orac_api.conversations_v to orac_apx_pub;
grant read on orac_api.llm_registry_v to orac_apx_pub;
grant read on orac_api.tts_voices_v to orac_apx_pub;
grant read on orac_api.model_generation_presets_v to orac_apx_pub;
grant read on orac_api.orac_personalities_v to orac_apx_pub;

grant select, insert, update, delete on orac_api.preference_definitions_v to orac;
grant select on orac_api.timezones_v to orac;
grant select, insert, update, delete on orac_api.users to orac;
grant select, insert, update, delete on orac_api.user_synonyms_v to orac;
grant select, insert, update, delete on orac_api.user_preferences_v to orac;
grant select, insert, update, delete on orac_api.messages_v to orac;
grant select, insert, update, delete on orac_api.conversations_v to orac;
grant select, insert, update, delete on orac_api.llm_registry_v to orac;
grant select, insert, update, delete on orac_api.tts_voices_v to orac;
grant select, insert, update, delete on orac_api.model_generation_presets_v to orac;
grant select, insert, update, delete on orac_api.orac_personalities_v to orac;

grant read on orac_api.preference_definitions_v to orac;
grant read on orac_api.timezones_v to orac;
grant read on orac_api.users to orac;
grant read on orac_api.user_synonyms_v to orac;
grant read on orac_api.user_preferences_v to orac;
grant read on orac_api.messages_v to orac;
grant read on orac_api.conversations_v to orac;
grant read on orac_api.llm_registry_v to orac;
grant read on orac_api.tts_voices_v to orac;
grant read on orac_api.model_generation_presets_v to orac;
grant read on orac_api.orac_personalities_v to orac;

grant select on orac_api.preference_definitions_v to orac_code with grant option;
grant select on orac_api.timezones_v to orac_code with grant option;
grant select on orac_api.users to orac_code with grant option;
grant select on orac_api.user_synonyms_v to orac_code with grant option;
grant select, insert, update, delete on orac_api.user_preferences_v to orac_code with grant option;
grant select on orac_api.messages_v to orac_code with grant option;
grant select on orac_api.conversations_v to orac_code with grant option;
grant select on orac_api.llm_registry_v to orac_code with grant option;
grant select, insert, update, delete on orac_api.tts_voices_v to orac_code with grant option;
grant select on orac_api.model_generation_presets_v to orac_code with grant option;
grant select on orac_api.orac_personalities_v to orac_code with grant option;

grant read on orac_api.preference_definitions_v to orac_code with grant option;
grant read on orac_api.timezones_v to orac_code with grant option;
grant read on orac_api.users to orac_code with grant option;
grant read on orac_api.user_synonyms_v to orac_code with grant option;
grant read on orac_api.user_preferences_v to orac_code with grant option;
grant read on orac_api.messages_v to orac_code with grant option;
grant read on orac_api.conversations_v to orac_code with grant option;
grant read on orac_api.llm_registry_v to orac_code with grant option;
grant read on orac_api.tts_voices_v to orac_code with grant option;
grant read on orac_api.model_generation_presets_v to orac_code with grant option;
grant read on orac_api.orac_personalities_v to orac_code with grant option;
