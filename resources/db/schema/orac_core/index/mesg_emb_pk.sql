-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac_core.mesg_emb_pk
  on orac_core.message_embeddings
  (
    emb_id asc
  )
;
