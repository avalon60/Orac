-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.user_preferences
  add constraint user_preferences_ck1
  check (value_type in ('boolean', 'number', 'string'))
;
