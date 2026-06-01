alter table orac_ha.ha_areas
  add constraint ha_areas_aliases_json
  check (aliases is json)
;
