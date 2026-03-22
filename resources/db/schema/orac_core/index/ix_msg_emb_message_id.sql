-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.ix_msg_emb_message_id
  on orac.message_embeddings
  (
    message_id asc
  )
;
