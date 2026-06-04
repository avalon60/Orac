alter table orac_ha.ha_areas
  add constraint ha_areas_labels_json
  check (labels is json)
;
