-- __author__: clive
-- __date__: 2026-04-25
-- __description__: unique key metadata for the published preferences view

alter view orac_api.user_preferences_v
  add constraint uq_user_prefs_v_user_key
  unique (user_id, pref_key)
  rely disable novalidate
;
