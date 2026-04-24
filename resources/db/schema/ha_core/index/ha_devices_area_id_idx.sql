create index ha_core.ha_devices_area_id_idx
  on ha_core.ha_devices
  (
    area_id asc
  )
logging
;
