alter table orac_ha.ha_devices
  add constraint ha_devices_cfg_subentries_json
  check (config_entries_subentries is json)
;
