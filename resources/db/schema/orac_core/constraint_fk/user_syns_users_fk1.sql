-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.user_synonyms
  add constraint user_syns_users_fk1
  foreign key
  (
    user_id
  )
  references orac.users
  (
    user_id
  )
  on delete cascade
;
