set echo on

spool run_all.log

prompt === tables ===
@table/conversations.sql
@table/devices.sql
@table/llm_registry.sql
@table/message_embeddings.sql
@table/messages.sql
@table/orac_personalities.sql
@table/user_preferences.sql
@table/user_prompt_elements.sql
@table/user_synonyms.sql
@table/users.sql

prompt === indexes ===
@index/conversations_pk.sql
@index/devices_pk.sql
@index/devices_uid_idx.sql
@index/ix_conversations_llm_id.sql
@index/ix_conversations_user_id.sql
@index/ix_messages_conv_id.sql
@index/ix_messages_llm_id.sql
@index/ix_msg_emb_message_id.sql
@index/ix_user_prefs_uid.sql
@index/llm_registry_pk.sql
@index/message_embeddings_pk.sql
@index/messages_pk.sql
@index/orpers_pk.sql
@index/orpers_uk1.sql
@index/upe_user_cat_idx.sql
@index/uq_conversations_session.sql
@index/uq_llm_registry_name.sql
@index/uq_messages_conv_turn.sql
@index/uq_msg_emb_message_chunk.sql
@index/uq_user_preferences_user_key.sql
@index/uq_users_username.sql
@index/user_preferences_pk.sql
@index/user_prompt_elements_pk_idx.sql
@index/user_synonyms_pk.sql
@index/user_synonyms_uid_idx.sql
@index/users_pk.sql

prompt === constraints_pk ===
@constraint_pk/conversations_pk.sql
@constraint_pk/devices_pk.sql
@constraint_pk/llm_registry_pk.sql
@constraint_pk/message_embeddings_pk.sql
@constraint_pk/messages_pk.sql
@constraint_pk/orac_personalities_pk.sql
@constraint_pk/user_preferences_pk.sql
@constraint_pk/user_prompt_elements_pk.sql
@constraint_pk/user_synonyms_pk.sql
@constraint_pk/users_pk.sql

prompt === constraints_uc ===
@constraint_uc/orac_personalities_uk1.sql
@constraint_uc/uq_conversations_session.sql
@constraint_uc/uq_llm_registry_name.sql
@constraint_uc/uq_messages_conv_turn.sql
@constraint_uc/uq_msg_emb_message_chunk.sql
@constraint_uc/uq_user_preferences_user_key.sql
@constraint_uc/uq_users_username.sql

prompt === constraints_fk ===
@constraint_fk/fk_conversations_llm.sql
@constraint_fk/fk_conversations_user.sql
@constraint_fk/fk_devices_user.sql
@constraint_fk/fk_messages_conversation.sql
@constraint_fk/fk_messages_llm.sql
@constraint_fk/fk_msg_emb_message.sql
@constraint_fk/fk_user_preferences_user.sql
@constraint_fk/fk_user_prompt_elements_user.sql
@constraint_fk/fk_user_synonyms_user.sql

prompt === constraints_other ===
@constraint_other/conversations_cc1.sql
@constraint_other/devices_ck1.sql
@constraint_other/llm_reg_cc1.sql
@constraint_other/llm_reg_ck2.sql
@constraint_other/message_embeddings_ck1.sql
@constraint_other/messages_ck1.sql
@constraint_other/orac_personalities_ck1.sql
@constraint_other/orac_personalities_ck2.sql
@constraint_other/orac_personalities_ck3.sql
@constraint_other/user_pref_ck1.sql
@constraint_other/user_preferences_ck1.sql
@constraint_other/user_prompt_elements_ck1.sql
@constraint_other/user_synonyms_ck1.sql
@constraint_other/users_ck1.sql

prompt === comments ===
@comment/orac_personalities.sql

spool off
