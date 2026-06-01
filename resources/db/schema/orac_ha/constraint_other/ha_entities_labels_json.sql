alter table orac_ha.ha_entities
  add constraint ha_entities_labels_json
  check (labels is json)
;
