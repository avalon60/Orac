alter table orac_ha.ha_devices
  add constraint ha_devices_config_entries_json
  check (config_entries is json)
;
