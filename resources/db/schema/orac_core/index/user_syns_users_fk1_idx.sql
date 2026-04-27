-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.user_syns_users_fk1_idx
  on orac.user_synonyms
  (
    user_id asc
  )
;
