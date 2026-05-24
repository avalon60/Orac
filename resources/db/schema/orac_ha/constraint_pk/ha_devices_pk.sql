alter table orac_ha.ha_devices
  add constraint ha_devices_pk
  primary key (device_id)
  using index orac_ha.ha_devices_pk_idx
;
