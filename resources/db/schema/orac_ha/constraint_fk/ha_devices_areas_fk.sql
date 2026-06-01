alter table orac_ha.ha_devices
  add constraint ha_devices_areas_fk
  foreign key
  (
    area_id
  )
  references orac_ha.ha_areas
  (
    area_id
  )
  not deferrable
;
