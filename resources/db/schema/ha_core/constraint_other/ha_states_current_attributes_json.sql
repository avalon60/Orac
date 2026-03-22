-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.ha_states_current
  add constraint ha_states_current_attributes_json
  check (attributes is json)
;
