create unique index orac_ha.ha_sync_runs_pk_idx
  on orac_ha.ha_sync_runs
  (
    sync_run_id asc
  )
logging
;
