alter table orac_ha.ha_entities
  add constraint ha_entities_options_json
  check (options is json)
;
