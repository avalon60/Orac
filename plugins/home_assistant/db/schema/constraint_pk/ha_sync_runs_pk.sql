alter table orac_ha.ha_sync_runs
  add constraint ha_sync_runs_pk
  primary key (sync_run_id)
  using index orac_ha.ha_sync_runs_pk_idx
;
