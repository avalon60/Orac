comment on table orac_ha.ha_sync_runs is
  'Records Home Assistant plugin synchronisation runs.'
;

comment on column orac_ha.ha_sync_runs.sync_run_id is
  'Client-generated synchronisation run identifier.'
;

comment on column orac_ha.ha_sync_runs.sync_type is
  'Synchronisation type: structural or state.'
;

comment on column orac_ha.ha_sync_runs.status is
  'Synchronisation status: running, complete, or failed.'
;

comment on column orac_ha.ha_sync_runs.rows_processed is
  'Number of payload rows processed by the sync run.'
;

comment on column orac_ha.ha_sync_runs.error_message is
  'Bounded error message recorded for failed sync runs.'
;
