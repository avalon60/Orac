-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


alter view orac.user_preferences_v
  add constraint user_prefs_v_pk
  primary key (pref_id)
  rely disable novalidate
;
