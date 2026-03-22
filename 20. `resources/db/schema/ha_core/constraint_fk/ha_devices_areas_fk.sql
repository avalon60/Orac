alter table plugins_core.ha_devices
  add constraint ha_devices_areas_fk
  foreign key
  (
    area_id
  )
  references plugins_core.ha_areas
  (
    area_id
  )
  not deferrable
;
