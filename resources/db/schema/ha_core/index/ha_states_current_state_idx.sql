create index ha_core.ha_states_current_state_idx
  on ha_core.ha_states_current
  (
    state asc
  )
logging
;
