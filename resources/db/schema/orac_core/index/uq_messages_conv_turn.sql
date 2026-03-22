-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac.uq_messages_conv_turn
  on orac.messages
  (
    conversation_id asc,
    turn_index asc
  )
;
