-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.ha_states_current
  add constraint ha_states_current_pk
  primary key (entity_id)
  using index orac.ha_states_current_pk_idx
;
