alter table orac_ha.ha_areas
  add constraint ha_areas_pk
  primary key (area_id)
  using index orac_ha.ha_areas_pk_idx
;
