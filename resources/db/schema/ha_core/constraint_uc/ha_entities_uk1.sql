alter table plugins_core.ha_entities
  add constraint ha_entities_uk1
  unique (ha_entity_id)
  using index plugins_core.ha_entities_uk1_idx
;
