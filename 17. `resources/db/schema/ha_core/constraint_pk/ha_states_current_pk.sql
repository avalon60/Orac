alter table plugins_core.ha_states_current
  add constraint ha_states_current_pk
  primary key (entity_id)
  using index plugins_core.ha_states_current_pk_idx
;
