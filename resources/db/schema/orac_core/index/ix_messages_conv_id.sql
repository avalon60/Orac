-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.ix_messages_conv_id
  on orac.messages
  (
    conversation_id asc
  )
;
