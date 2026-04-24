create index ha_core.ha_entities_device_id_idx
  on ha_core.ha_entities
  (
    device_id asc
  )
logging
;
