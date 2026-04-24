alter table ha_core.ha_devices
  add constraint ha_devices_connections_json
  check (connections is json)
;
