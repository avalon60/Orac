-- __author__: clive
-- __date__: 2026-04-27
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.preference_definitions
  add constraint prfdfn_ck3
  check (lov_type is null or lov_type in ('static', 'sql'))
;
