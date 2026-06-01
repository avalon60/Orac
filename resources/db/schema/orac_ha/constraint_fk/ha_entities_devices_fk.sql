alter table orac_ha.ha_entities
  add constraint ha_entities_devices_fk
  foreign key
  (
    device_id
  )
  references orac_ha.ha_devices
  (
    device_id
  )
  not deferrable
;
