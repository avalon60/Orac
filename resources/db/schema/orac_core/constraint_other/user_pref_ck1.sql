-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.user_preferences
  add constraint user_pref_ck1
  check
  (
    (
      value_type = 'string'
      and json_exists(pref_value, '$?(@.type() == "string")')
    )
    or
    (
      value_type = 'number'
      and json_exists(pref_value, '$?(@.type() == "number")')
    )
    or
    (
      value_type = 'boolean'
      and json_exists(pref_value, '$?(@.type() == "boolean")')
    )
    or
    (
      value_type = 'json'
      and json_exists(pref_value, '$')
    )
  )
;
