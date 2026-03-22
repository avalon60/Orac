create index plugins_core.ha_devices_area_id_idx
  on plugins_core.ha_devices
  (
    area_id asc
  )
logging
;
