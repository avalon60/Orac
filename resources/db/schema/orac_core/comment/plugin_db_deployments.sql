comment on table orac_core.plugin_db_deployments is
  'Tracks plugin-owned database deployment attempts and outcomes.';

comment on column orac_core.plugin_db_deployments.plugin_db_deployment_id is
  'Primary key for the plugin database deployment row.';

comment on column orac_core.plugin_db_deployments.plugin_id is
  'Stable plugin id from the plugin manifest.';

comment on column orac_core.plugin_db_deployments.plugin_version is
  'Plugin version from the plugin manifest.';

comment on column orac_core.plugin_db_deployments.schema_name is
  'Plugin-owned database schema name deployed by this attempt.';

comment on column orac_core.plugin_db_deployments.deployment_checksum is
  'SHA-256 checksum identifying the canonical plugin database payload.';

comment on column orac_core.plugin_db_deployments.deployment_status is
  'Deployment lifecycle status: started, succeeded, or failed.';

comment on column orac_core.plugin_db_deployments.started_on is
  'Timestamp when the deployment attempt started.';

comment on column orac_core.plugin_db_deployments.completed_on is
  'Timestamp when the deployment attempt completed or failed.';

comment on column orac_core.plugin_db_deployments.error_message is
  'Failure detail captured for failed plugin database deployments.';

comment on column orac_core.plugin_db_deployments.log_path is
  'Container-side log directory or file path for deployment diagnostics.';
