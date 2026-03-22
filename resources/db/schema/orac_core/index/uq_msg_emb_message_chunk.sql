-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac.uq_msg_emb_message_chunk
  on orac.message_embeddings
  (
    message_id asc,
    chunk_index asc
  )
;
