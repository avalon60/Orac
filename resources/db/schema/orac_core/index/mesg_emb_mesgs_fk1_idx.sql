-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.mesg_emb_mesgs_fk1_idx
  on orac.message_embeddings
  (
    message_id asc
  )
;
