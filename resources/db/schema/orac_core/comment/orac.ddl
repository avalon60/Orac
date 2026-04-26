comment on table orac.conversations is 'One row per dialog thread; holds session key and default LLM.'
comment on column orac.conversations.conversation_id is 'Primary key for conversations.'
comment on column orac.conversations.session_id is 'External/session key (unique).'
comment on column orac.conversations.llm_id is 'Default LLM for this conversation; messages may override.'

comment on table orac.llm_registry is 'Registry of available large language models (LLMs) and their configuration.'
comment on column orac.llm_registry.llm_id is 'Primary key for the orac.llm_registry table.'
comment on column orac.llm_registry.name is 'Human-readable unique name for the model configuration.'
comment on column orac.llm_registry.provider is 'Vendor/source of the model.'
comment on column orac.llm_registry.model is 'Provider model identifier.'
comment on column orac.llm_registry.context_policy is 'How conversation state is managed for this model.'
comment on column orac.llm_registry.max_context_tokens is 'Maximum supported context window in tokens.'
comment on column orac.llm_registry.properties is 'Free-form JSON for provider/model metadata.'

comment on table orac.message_embeddings is 'Embeddings for message-level chunks.'
comment on column orac.message_embeddings.message_id is 'FK to orac.messages.message_id.'
comment on column orac.message_embeddings.chunk_index is '1-based ordinal of chunk within the message.'

comment on table orac.messages is 'Atomic utterances within a conversation (user/assistant/system/tool).'
comment on column orac.messages.turn_index is 'Ordinal per conversation starting at 1.'
comment on column orac.messages.llm_id is 'Optional override of conversation default LLM.'
comment on column orac.messages.role is
  'The conversational actor for the message, aligned to LLM-style roles such as system, user, assistant, and tool.';
comment on column orac.messages.message_type is
  'The semantic purpose of the message row, such as chat, system_prompt, context_injection, tool_call, tool_result, summary, error, or audit.';

comment on table orac.user_preferences is 'Stores key-value preference settings for each user.'
comment on column orac.user_preferences.pref_id is 'Primary key for the preference row.'
comment on column orac.user_preferences.user_id is 'Owning user for the preference.'
comment on column orac.user_preferences.pref_key is 'Namespaced preference name scoped to a single user.'
comment on column orac.user_preferences.pref_value is 'Stored preference value.'

comment on table orac.users is 'Stores registered users of the orac system.'
comment on column orac.users.user_id is 'Primary key for the orac.users table.'
comment on column orac.users.username is 'Unique login handle for the orac.users table.'
comment on column orac.users.display_name is 'Human-friendly name for the user.'
comment on column orac.users.email is 'Primary contact email for the user.'
