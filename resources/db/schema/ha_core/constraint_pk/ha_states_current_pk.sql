alter table ha_core.ha_states_current
  add constraint ha_states_current_pk
  primary key (entity_id)
  using index ha_core.ha_states_current_pk_idx
;
