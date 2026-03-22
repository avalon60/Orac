-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.ix_user_prefs_uid
  on orac.user_preferences
  (
    user_id asc
  )
;
