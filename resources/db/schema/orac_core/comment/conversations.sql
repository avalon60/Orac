comment on table orac_core.conversations is
  'One row per dialog thread; holds session key and default LLM.'
;

comment on column orac_core.conversations.conversation_id is
  'Primary key for conversations.'
;

comment on column orac_core.conversations.session_id is
  'External/session key (unique).'
;

comment on column orac_core.conversations.llm_id is
  'Default LLM for this conversation; messages may override.'
;
