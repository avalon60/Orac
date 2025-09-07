--------------------------------------------------------------------------------
-- FOREIGN KEY CONSTRAINTS
--------------------------------------------------------------------------------

-- fk: conversations.user_id → users.user_id (cascade delete)
alter table orac.conversations
  add constraint convs_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

-- fk: conversations.llm_id → llm_registry.llm_id
alter table orac.conversations
  add constraint convs_llmreg_fk1 foreign key (llm_id)
  references orac.llm_registry (llm_id);

-- fk: messages.conversation_id → conversations.conversation_id (cascade delete)
alter table orac.messages
  add constraint messgs_convs_fk1 foreign key (conversation_id)
  references orac.conversations (conversation_id)
  on delete cascade;

-- fk: messages.llm_id → llm_registry.llm_id
alter table orac.messages
  add constraint messgs_llmreg_fk1 foreign key (llm_id)
  references orac.llm_registry (llm_id);

-- fk: message_embeddings.message_id → messages.message_id (cascade delete)
alter table orac.message_embeddings
  add constraint megemb_messgs_fk1 foreign key (message_id)
  references orac.messages (message_id)
  on delete cascade;

-- fk: user_preferences.user_id → users.user_id (cascade delete)
alter table orac.user_preferences
  add constraint usrprf_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

-- fk: user_prompt_elements.user_id → users.user_id (cascade delete)
alter table orac.user_prompt_elements
  add constraint usrpre_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

-- fk: user_synonyms.user_id → users.user_id (cascade delete)
alter table orac.user_synonyms
  add constraint usrsyns_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

-- fk: devices.user_id → users.user_id (cascade delete)
alter table orac.devices
  add constraint devics_users_fk1 foreign key (user_id)
  references orac.users (user_id)
  on delete cascade;

