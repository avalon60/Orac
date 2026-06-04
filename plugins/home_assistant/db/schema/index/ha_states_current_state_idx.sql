create index orac_ha.ha_states_current_state_idx
  on orac_ha.ha_states_current
  (
    state asc
  )
logging
;
