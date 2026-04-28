-- __author__: clive
-- __date__: 2026-04-27
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.preference_definitions
  add constraint prfdfn_ck1
  check (value_type in ('string', 'number', 'boolean', 'json'))
;
