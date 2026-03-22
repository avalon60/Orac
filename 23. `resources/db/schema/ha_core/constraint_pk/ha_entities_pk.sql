alter table plugins_core.ha_entities
  add constraint ha_entities_pk
  primary key (entity_id)
  using index plugins_core.ha_entities_pk_idx;
