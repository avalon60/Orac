-- __author__: clive
-- __date__: 2026-06-03
-- __description__: unique deployment checksum index for plugin_db_deployments


create unique index orac_core.plg_dbdep_uk1_idx
  on orac_core.plugin_db_deployments
     (plugin_id, plugin_version, schema_name, deployment_checksum)
;
