alter table plugins_core.ha_devices
  add constraint ha_devices_labels_json
  check (labels is json)
;
