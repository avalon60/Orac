-- __author__: clive
-- __date__: 2026-06-03
-- __description__: primary key index for plugin_db_deployments


create unique index orac_core.plg_dbdep_pk
  on orac_core.plugin_db_deployments
     (plugin_db_deployment_id)
;
