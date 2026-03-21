-- __author__: clive bostock
-- __date__: 2025-12-28
-- __description__: generated/synchronised by Cline; one object per file

alter table orac.ha_states_current
  add constraint ha_states_current_attributes_json
  check (attributes is json);
