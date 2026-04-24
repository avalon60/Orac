alter table ha_core.ha_entities
  add constraint ha_entities_uk1
  unique (ha_entity_id)
  using index ha_core.ha_entities_uk1_idx
;
