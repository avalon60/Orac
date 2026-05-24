alter table orac_ha.ha_states_current
  add constraint ha_states_current_pk
  primary key (entity_id)
  using index orac_ha.ha_states_current_pk_idx
;
