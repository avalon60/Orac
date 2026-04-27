-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.message_embeddings
  add constraint mesg_emb_mesgs_fk1
  foreign key
  (
    message_id
  )
  references orac.messages
  (
    message_id
  )
  on delete cascade
;
