alter table orac_ha.ha_sync_runs
  add constraint ha_sync_runs_type_ck
  check (sync_type in ('structural', 'state'))
;
