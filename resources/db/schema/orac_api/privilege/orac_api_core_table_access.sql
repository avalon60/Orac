-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant the api schema controlled access to legacy ORAC tables

grant select, insert, update, delete on orac.users to orac_api with grant option;
grant select, insert, update, delete on orac.user_synonyms to orac_api with grant option;
grant select, insert, update, delete on orac.user_preferences to orac_api with grant option;
grant select, insert, update, delete on orac.messages to orac_api with grant option;
grant select, insert, update, delete on orac.conversations to orac_api with grant option;
grant select, insert, update, delete on orac.llm_registry to orac_api with grant option;
grant select, insert, update, delete on orac.devices to orac_api with grant option;
grant select, insert, update, delete on orac.message_embeddings to orac_api with grant option;
grant select, insert, update, delete on orac.user_prompt_elements to orac_api with grant option;
grant select, insert, update, delete on orac.orac_personalities to orac_api with grant option;
