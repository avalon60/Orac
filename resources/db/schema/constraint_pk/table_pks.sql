--------------------------------------------------------------------------------
-- PRIMARY KEY CONSTRAINTS
--------------------------------------------------------------------------------

-- pk: users(user_id)
alter table orac.users
  add constraint users_pk primary key (user_id)
  using index orac.users_pk_idx;

-- pk: conversations(conversation_id)
alter table orac.conversations
  add constraint convs_pk primary key (conversation_id)
  using index orac.convs_pk_idx;

-- pk: messages(message_id)
alter table orac.messages
  add constraint messgs_pk primary key (message_id)
  using index orac.messgs_pk_idx;

-- pk: message_embeddings(emb_id)
alter table orac.message_embeddings
  add constraint megemb_pk primary key (emb_id)
  using index orac.megemb_pk_idx;

-- pk: llm_registry(llm_id)
alter table orac.llm_registry
  add constraint llmreg_pk primary key (llm_id)
  using index orac.llmreg_pk_idx;

-- pk: user_preferences(pref_id)
alter table orac.user_preferences
  add constraint usrprf_pk primary key (pref_id)
  using index orac.usrprf_pk_idx;

-- pk: user_prompt_elements(element_id)
alter table orac.user_prompt_elements
  add constraint usrpre_pk primary key (element_id)
  using index orac.usrpre_pk_idx;

-- pk: user_synonyms(alias_type, alias_value)
alter table orac.user_synonyms
  add constraint usrsyns_pk primary key (alias_type, alias_value)
  using index orac.usrsyns_pk_idx;

-- pk: devices(device_id)
alter table orac.devices
  add constraint devics_pk primary key (device_id)
  using index orac.devics_pk_idx;
