alter table ha_core.ha_entities
  add constraint ha_entities_devices_fk
  foreign key
  (
    device_id
  )
  references ha_core.ha_devices
  (
    device_id
  )
  not deferrable
;
