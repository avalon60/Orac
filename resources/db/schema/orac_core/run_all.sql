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
@index/convs_llm_reg_fk1_idx.sql
@index/convs_pk.sql
@index/convs_uk1_idx.sql
@index/convs_users_fk1_idx.sql
@index/device_pk.sql
@index/device_users_fk1_idx.sql
@index/llm_reg_pk.sql
@index/llm_reg_uk1_idx.sql
@index/mesg_emb_mesgs_fk1_idx.sql
@index/mesg_emb_pk.sql
@index/mesg_emb_uk1_idx.sql
@index/mesgs_convs_fk1_idx.sql
@index/mesgs_llm_reg_fk1_idx.sql
@index/mesgs_pk.sql
@index/mesgs_uk1_idx.sql
@index/orpers_pk.sql
@index/orpers_uk1_idx.sql
@index/user_pe_idx1.sql
@index/user_pe_pk.sql
@index/user_pref_pk.sql
@index/user_pref_uk1_idx.sql
@index/user_pref_users_fk1_idx.sql
@index/user_syns_pk.sql
@index/user_syns_users_fk1_idx.sql
@index/users_pk.sql
@index/users_uk1_idx.sql

prompt === constraints_pk ===
@constraint_pk/convs_pk.sql
@constraint_pk/device_pk.sql
@constraint_pk/llm_reg_pk.sql
@constraint_pk/mesg_emb_pk.sql
@constraint_pk/mesgs_pk.sql
@constraint_pk/orpers_pk.sql
@constraint_pk/user_pe_pk.sql
@constraint_pk/user_pref_pk.sql
@constraint_pk/user_syns_pk.sql
@constraint_pk/users_pk.sql

prompt === constraints_uc ===
@constraint_uc/convs_uk1.sql
@constraint_uc/llm_reg_uk1.sql
@constraint_uc/mesg_emb_uk1.sql
@constraint_uc/mesgs_uk1.sql
@constraint_uc/orpers_uk1.sql
@constraint_uc/user_pref_uk1.sql
@constraint_uc/users_uk1.sql

prompt === constraints_fk ===
@constraint_fk/convs_llm_reg_fk1.sql
@constraint_fk/convs_users_fk1.sql
@constraint_fk/device_users_fk1.sql
@constraint_fk/mesg_emb_mesgs_fk1.sql
@constraint_fk/mesgs_convs_fk1.sql
@constraint_fk/mesgs_llm_reg_fk1.sql
@constraint_fk/user_pe_users_fk1.sql
@constraint_fk/user_pref_users_fk1.sql
@constraint_fk/user_syns_users_fk1.sql

prompt === constraints_other ===
@constraint_other/convs_ck1.sql
@constraint_other/device_ck1.sql
@constraint_other/llm_reg_ck1.sql
@constraint_other/llm_reg_ck2.sql
@constraint_other/mesg_emb_ck1.sql
@constraint_other/mesgs_ck1.sql
@constraint_other/mesgs_ck2.sql
@constraint_other/orpers_ck1.sql
@constraint_other/orpers_ck2.sql
@constraint_other/orpers_ck3.sql
@constraint_other/user_pref_ck1.sql
@constraint_other/user_pref_ck2.sql
@constraint_other/user_pe_ck1.sql
@constraint_other/user_syns_ck1.sql
@constraint_other/users_ck1.sql

prompt === comments ===
@comment/conversations.sql
@comment/llm_registry.sql
@comment/message_embeddings.sql
@comment/messages.sql
@comment/orac_personalities.sql
@comment/user_preferences.sql
@comment/users.sql

prompt === triggers ===
@trigger/convs_bu.sql
@trigger/device_bu.sql
@trigger/llm_reg_bu.sql
@trigger/mesg_emb_bu.sql
@trigger/mesgs_bu.sql
@trigger/user_pe_bu.sql
@trigger/user_pref_bu.sql
@trigger/user_syns_bu.sql
@trigger/users_bu.sql

spool off
