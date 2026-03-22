create index plugins_core.ha_entities_device_id_idx
  on plugins_core.ha_entities
  (
    device_id asc
  )
logging;
