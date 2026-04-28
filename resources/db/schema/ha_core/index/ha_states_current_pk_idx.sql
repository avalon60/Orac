create unique index ha_core.ha_states_current_pk_idx
  on ha_core.ha_states_current
  (
    entity_id asc
  )
logging
;
