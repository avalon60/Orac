--------------------------------------------------------------------------------
-- VIEW CONSTRAINTS (Pseudo/Metadata)
--------------------------------------------------------------------------------

-- pseudo uk on view: user_preferences_v(user_id, pref_key) for APEX metadata only
alter view orac.user_preferences_v
  add constraint uq_user_prefs_v_user_key
  unique (user_id, pref_key)
  rely disable novalidate;
