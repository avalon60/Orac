-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac_core.user_pref_uk1_idx
  on orac_core.user_preferences
  (
    user_id asc,
    pref_key asc
  )
;
