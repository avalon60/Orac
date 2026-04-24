-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


alter view orac.user_preferences_v
  add constraint uq_user_prefs_v_user_key
  unique (user_id, pref_key)
  rely disable novalidate
;
