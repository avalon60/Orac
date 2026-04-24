alter table ha_core.ha_areas
  add constraint ha_areas_pk
  primary key (area_id)
  using index ha_core.ha_areas_pk_idx
;
