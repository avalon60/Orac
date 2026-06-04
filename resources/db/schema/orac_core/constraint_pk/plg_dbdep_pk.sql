-- __author__: clive
-- __date__: 2026-06-03
-- __description__: primary key for plugin_db_deployments


alter table orac_core.plugin_db_deployments add constraint plg_dbdep_pk
  primary key (plugin_db_deployment_id)
;
