-- __author__: clive
-- __date__: 2026-06-03
-- __description__: deployment checksum uniqueness for plugin_db_deployments


alter table orac_core.plugin_db_deployments add constraint plg_dbdep_uk1
  unique (plugin_id, plugin_version, schema_name, deployment_checksum)
;
