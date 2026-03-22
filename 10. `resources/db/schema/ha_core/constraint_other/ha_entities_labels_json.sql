alter table plugins_core.ha_entities
  add constraint ha_entities_labels_json
  check (labels is json)
;
