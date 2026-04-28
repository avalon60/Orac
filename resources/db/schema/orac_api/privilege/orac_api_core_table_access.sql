-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant the api schema controlled access to ORAC_CORE tables

grant select, insert, update, delete on orac_core.users to orac_api with grant option;
grant select, insert, update, delete on orac_core.preference_definitions to orac_api with grant option;
grant select on orac_core.timezones to orac_api with grant option;
grant select, insert, update, delete on orac_core.user_synonyms to orac_api with grant option;
grant select, insert, update, delete on orac_core.user_preferences to orac_api with grant option;
grant select, insert, update, delete on orac_core.messages to orac_api with grant option;
grant select, insert, update, delete on orac_core.conversations to orac_api with grant option;
grant select, insert, update, delete on orac_core.llm_registry to orac_api with grant option;
grant select, insert, update, delete on orac_core.devices to orac_api with grant option;
grant select, insert, update, delete on orac_core.message_embeddings to orac_api with grant option;
grant select, insert, update, delete on orac_core.user_prompt_elements to orac_api with grant option;
grant select, insert, update, delete on orac_core.orac_personalities to orac_api with grant option;
