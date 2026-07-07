--liquibase formatted sql

--changeset clive:plugin_registry_v_create stripComments:false runOnChange:true context:core labels:core

create or replace force view orac_api.plugin_registry_v as
select plugin_registry_id
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
     , capabilities_summary
     , entitlements_summary
     , database_schemas_summary
     , ui_icon_class
     , ui_accent_class
     , dependency_declarations
     , dependency_fingerprint
     , install_status
     , configuration_status
     , dependency_status
     , database_status
     , readiness_status
     , enabled
     , last_error_code
     , last_error_message
     , created_on
     , created_by
     , updated_on
     , updated_by
     , row_version
  from orac_core.plugin_registry;
--rollback drop view orac_api.plugin_registry_v;
