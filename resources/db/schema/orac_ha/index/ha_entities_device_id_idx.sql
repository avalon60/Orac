create index orac_ha.ha_entities_device_id_idx
  on orac_ha.ha_entities
  (
    device_id asc
  )
logging
;
