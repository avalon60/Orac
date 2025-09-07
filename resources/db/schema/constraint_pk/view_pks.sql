--------------------------------------------------------------------------------
-- VIEW CONSTRAINTS (Pseudo/Metadata)
--------------------------------------------------------------------------------
-- pseudo pk on view: user_preferences_v(pref_id) for APEX metadata only
alter view orac.user_preferences_v
  add constraint user_prefs_v_pk
  primary key (pref_id)
  rely disable novalidate;

