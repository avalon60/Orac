comment on table orac_core.user_preferences is
  'Stores key-value preference settings for each user.'
;

comment on column orac_core.user_preferences.pref_id is
  'Primary key for the preference row.'
;

comment on column orac_core.user_preferences.user_id is
  'Owning user for the preference.'
;

comment on column orac_core.user_preferences.pref_key is
  'Namespaced preference name scoped to a single user.'
;

comment on column orac_core.user_preferences.pref_value is
  'Stored preference value.'
;
