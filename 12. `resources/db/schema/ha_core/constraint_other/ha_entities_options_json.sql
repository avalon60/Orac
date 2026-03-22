alter table plugins_core.ha_entities
  add constraint ha_entities_options_json
  check (options is json)
;
