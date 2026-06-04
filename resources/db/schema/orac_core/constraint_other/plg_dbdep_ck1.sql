-- __author__: clive
-- __date__: 2026-06-03
-- __description__: valid deployment status values for plugin_db_deployments


alter table orac_core.plugin_db_deployments add constraint plg_dbdep_ck1
  check (deployment_status in ('started', 'succeeded', 'failed'))
;
