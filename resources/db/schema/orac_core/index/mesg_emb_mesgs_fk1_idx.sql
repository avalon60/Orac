-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac_core.mesg_emb_mesgs_fk1_idx
  on orac_core.message_embeddings
  (
    message_id asc
  )
;
