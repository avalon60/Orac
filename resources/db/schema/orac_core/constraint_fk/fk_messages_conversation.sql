-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.messages
  add constraint fk_messages_conversation
  foreign key
  (
    conversation_id
  )
  references orac.conversations
  (
    conversation_id
  )
  on delete cascade
;
