alter table orac_ha.ha_sync_runs
  add constraint ha_sync_runs_status_ck
  check (status in ('running', 'complete', 'failed'))
;
