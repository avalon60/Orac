-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file

alter table orac.messages add constraint messages_ck2
check (
  message_type in (
    'conversation',
    'system_prompt',
    'plugin_request',
    'plugin_response',
    'routing_hint',
    'rag_context',
    'summary'
  )
);
