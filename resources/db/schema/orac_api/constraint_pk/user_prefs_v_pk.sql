-- __author__: clive
-- __date__: 2026-04-25
-- __description__: primary key metadata for the published preferences view

alter view orac_api.user_preferences_v
  add constraint user_prefs_v_pk
  primary key (pref_id)
  rely disable novalidate
;
