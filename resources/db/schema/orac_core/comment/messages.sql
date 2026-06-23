--liquibase formatted sql

--changeset clive:comment_orac_core_comment_messages context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.messages is
  'Atomic utterances within a conversation (user/assistant/system/tool).'
;

comment on column orac_core.messages.turn_index is
  'Ordinal per conversation starting at 1.'
;

comment on column orac_core.messages.llm_id is
  'Optional override of conversation default LLM.'
;

comment on column orac_core.messages.role is
  'The conversational actor for the message, aligned to LLM-style roles such as system, user, assistant, and tool.'
;

comment on column orac_core.messages.message_type is
  'The semantic purpose of the message row, such as chat, system_prompt, context_injection, tool_call, tool_result, summary, error, or audit.'
;
