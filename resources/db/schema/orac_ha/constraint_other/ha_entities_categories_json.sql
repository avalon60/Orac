alter table orac_ha.ha_entities
  add constraint ha_entities_categories_json
  check (categories is json)
;
