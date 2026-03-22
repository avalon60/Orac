create index plugins_core.ha_states_current_state_idx
  on plugins_core.ha_states_current
  (
    state asc
  )
logging;
