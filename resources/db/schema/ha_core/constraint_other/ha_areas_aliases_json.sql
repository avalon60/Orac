alter table ha_core.ha_areas
  add constraint ha_areas_aliases_json
  check (aliases is json)
;
