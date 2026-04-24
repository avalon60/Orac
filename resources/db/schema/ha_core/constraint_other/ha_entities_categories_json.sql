alter table ha_core.ha_entities
  add constraint ha_entities_categories_json
  check (categories is json)
;
