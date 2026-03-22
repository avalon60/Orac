alter table plugins_core.ha_areas
  add constraint ha_areas_pk
  primary key (area_id)
  using index plugins_core.ha_areas_pk_idx
;
