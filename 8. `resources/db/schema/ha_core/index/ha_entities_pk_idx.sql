create unique index plugins_core.ha_entities_pk_idx
  on plugins_core.ha_entities
  (
    entity_id asc
  )
logging;
