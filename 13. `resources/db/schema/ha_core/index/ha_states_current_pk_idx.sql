create unique index plugins_core.ha_states_current_pk_idx
  on plugins_core.ha_states_current
  (
    entity_id asc
  )
logging
;
