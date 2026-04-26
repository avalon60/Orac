-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.message_embeddings
  add constraint message_embeddings_ck1
  check (distance_metric in ('COSINE', 'DOT', 'HAMMING', 'JACCARD', 'L2', 'L2_SQUARED', 'MANHATTAN'))
;
