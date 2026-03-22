-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.messages
  add constraint uq_messages_conv_turn
  unique (conversation_id, turn_index)
;
