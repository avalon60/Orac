-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file

alter table orac.messages
  add constraint messages_ck2
  check (
    message_type in (
      'audit',
      'chat',
      'context_injection',
      'error',
      'summary',
      'system_prompt',
      'tool_call',
      'tool_result'
    )
  )
;
