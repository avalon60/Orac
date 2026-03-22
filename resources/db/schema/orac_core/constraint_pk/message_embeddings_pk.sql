-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.message_embeddings
  add constraint message_embeddings_pk
  primary key (emb_id)
;
