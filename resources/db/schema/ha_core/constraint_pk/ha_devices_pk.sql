alter table plugins_core.ha_devices
  add constraint ha_devices_pk
  primary key (device_id)
  using index plugins_core.ha_devices_pk_idx
;
