alter table plugins_core.ha_entities
  add constraint ha_entities_devices_fk
  foreign key
  (
    device_id
  )
  references plugins_core.ha_devices
  (
    device_id
  )
  not deferrable
;
