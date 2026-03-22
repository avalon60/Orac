alter table plugins_core.ha_areas
  add constraint ha_areas_labels_json
  check (labels is json)
;
