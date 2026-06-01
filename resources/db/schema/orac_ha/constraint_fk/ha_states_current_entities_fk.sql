alter table orac_ha.ha_states_current
  add constraint ha_states_current_entities_fk
  foreign key
  (
    entity_id
  )
  references orac_ha.ha_entities
  (
    entity_id
  )
  not deferrable
;
