-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.user_preferences
  add constraint user_pref_ck1
  check
  (
    (
      value_type = 'string'
      and json_value(pref_value, '$' returning varchar2(4000) null on error) is not null
    )
    or
    (
      value_type = 'number'
      and json_value(pref_value, '$' returning number null on error) is not null
    )
    or
    (
      value_type = 'boolean'
      and lower(json_value(pref_value, '$' returning varchar2(5) null on error)) in ('true', 'false')
    )
  )
;
