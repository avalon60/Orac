alter table orac_ha.ha_devices
  add constraint ha_devices_identifiers_json
  check (identifiers is json)
;
