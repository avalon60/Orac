-- uk index: orac.user_preferences(user_id, pref_key)
create unique index orac.usrprf_uk1_idx on orac.user_preferences(user_id, pref_key);
