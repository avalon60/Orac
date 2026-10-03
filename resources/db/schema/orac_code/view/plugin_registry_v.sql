--liquibase formatted sql

--changeset clive:create_view_orac_code_view_plugin_registry_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-07
-- __description__: approved runtime projection of active plugin registry state

create or replace view orac_code.plugin_registry_v as
select plugin_registry_id
     , knowledge_scope_id
     , plugin_id
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
     , command_dependency_declarations
     , command_dependency_fingerprint
     , command_prerequisite_status
     , command_dependency_report
     , ui_icon_class
     , ui_accent_class
     , install_status
     , configuration_status
     , dependency_status
     , database_status
     , readiness_status
     , enabled
     , last_error_code
     , last_error_message
     , row_version
     , database_schemas_summary
     , (select removal.removal_id from orac_api.plugin_removals_v removal
         where removal.plugin_registry_id = plugin.plugin_registry_id
           and removal.completed_on is null) removal_id
  from orac_api.plugin_registry_v plugin;

--rollback drop view orac_code.plugin_registry_v;
