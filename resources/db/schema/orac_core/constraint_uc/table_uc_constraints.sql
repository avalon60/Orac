--------------------------------------------------------------------------------
-- UNIQUE KEY CONSTRAINTS
--------------------------------------------------------------------------------

-- uk: users(username)
alter table orac.users
  add constraint users_uk1 unique (username)
  using index orac.users_uk1_idx;

-- uk: conversations(session_id)
alter table orac.conversations
  add constraint convs_uk1 unique (user_id, session_id)
  using index orac.convs_uk1_idx;

-- uk: messages(conversation_id, turn_index)
alter table orac.messages
  add constraint messgs_uk1 unique (conversation_id, turn_index)
  using index orac.messgs_uk1_idx;

-- uk: message_embeddings(message_id, chunk_index)
alter table orac.message_embeddings
  add constraint megemb_uk1 unique (message_id, chunk_index)
  using index orac.megemb_uk1_idx;

-- uk: llm_registry(name)
alter table orac.llm_registry
  add constraint llmreg_uk1 unique (name)
  using index orac.llmreg_uk1_idx;

-- uk: user_preferences(user_id, pref_key)
alter table orac.user_preferences
  add constraint usrprf_uk1 unique (user_id, pref_key)
  using index orac.usrprf_uk1_idx;


