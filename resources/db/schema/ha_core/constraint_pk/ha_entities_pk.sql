alter table ha_core.ha_entities
  add constraint ha_entities_pk
  primary key (entity_id)
  using index ha_core.ha_entities_pk_idx
;
