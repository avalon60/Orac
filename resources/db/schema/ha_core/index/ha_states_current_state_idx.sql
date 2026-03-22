-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.ha_states_current_state_idx
  on orac.ha_states_current
  (
    state asc
  )
logging
;
