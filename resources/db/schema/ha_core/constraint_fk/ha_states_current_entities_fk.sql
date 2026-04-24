alter table ha_core.ha_states_current
  add constraint ha_states_current_entities_fk
  foreign key
  (
    entity_id
  )
  references ha_core.ha_entities
  (
    entity_id
  )
  not deferrable
;
