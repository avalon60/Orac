-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac.uq_user_preferences_user_key
  on orac.user_preferences
  (
    user_id asc,
    pref_key asc
  )
;
