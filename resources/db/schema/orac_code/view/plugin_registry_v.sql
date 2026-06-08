-- __author__: clive
-- __date__: 2026-06-07
-- __description__: approved runtime projection of active plugin registry state

create or replace view orac_code.plugin_registry_v as
select plugin_id
     , plugin_name
     , plugin_version
     , runtime_mode
     , manifest_hash
     , package_hash
     , install_source_type
     , install_source_ref
     , installed_path
     , config_path
     , dependency_fingerprint
     , install_status
     , configuration_status
     , dependency_status
     , database_status
     , readiness_status
     , enabled
     , last_error_code
     , last_error_message
     , row_version
  from orac_api.plugin_registry_v;
