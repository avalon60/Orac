--liquibase formatted sql

--changeset clive:plugin_registry_tapi_create_body stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package body orac_api.plugin_registry_tapi
as
  procedure ins(
    p_row in out orac_api.plugin_registry_v%rowtype
  )
  is
  begin
    insert into orac_api.plugin_registry_v
      (
        plugin_id, plugin_name, plugin_version, runtime_mode, manifest_hash,
        package_hash, install_source_type, install_source_ref, installed_path,
        config_path, capabilities_summary, entitlements_summary,
        database_schemas_summary, ui_icon_class, ui_accent_class,
        dependency_declarations,
        dependency_fingerprint, install_status, configuration_status,
        dependency_status, database_status, readiness_status, enabled,
        last_error_code, last_error_message
      )
    values
      (
        p_row.plugin_id, p_row.plugin_name, p_row.plugin_version,
        p_row.runtime_mode, p_row.manifest_hash, p_row.package_hash,
        p_row.install_source_type, p_row.install_source_ref,
        p_row.installed_path, p_row.config_path, p_row.capabilities_summary,
        p_row.entitlements_summary, p_row.database_schemas_summary,
        p_row.ui_icon_class, p_row.ui_accent_class,
        p_row.dependency_declarations, p_row.dependency_fingerprint,
        p_row.install_status, p_row.configuration_status,
        p_row.dependency_status, p_row.database_status,
        p_row.readiness_status, p_row.enabled, p_row.last_error_code,
        p_row.last_error_message
      )
    returning plugin_registry_id, row_version
         into p_row.plugin_registry_id, p_row.row_version;
  end ins;

  procedure upd(
    p_plugin_registry_id in     orac_api.plugin_registry_v.plugin_registry_id%type,
    p_row                in out orac_api.plugin_registry_v%rowtype
  )
  is
  begin
    update orac_api.plugin_registry_v
       set plugin_name              = p_row.plugin_name
         , plugin_version           = p_row.plugin_version
         , runtime_mode             = p_row.runtime_mode
         , manifest_hash            = p_row.manifest_hash
         , package_hash             = p_row.package_hash
         , install_source_type      = p_row.install_source_type
         , install_source_ref       = p_row.install_source_ref
         , installed_path           = p_row.installed_path
         , config_path              = p_row.config_path
         , capabilities_summary     = p_row.capabilities_summary
         , entitlements_summary     = p_row.entitlements_summary
         , database_schemas_summary = p_row.database_schemas_summary
         , ui_icon_class            = p_row.ui_icon_class
         , ui_accent_class          = p_row.ui_accent_class
         , dependency_declarations  = p_row.dependency_declarations
         , dependency_fingerprint   = p_row.dependency_fingerprint
         , install_status           = p_row.install_status
         , configuration_status     = p_row.configuration_status
         , dependency_status        = p_row.dependency_status
         , database_status          = p_row.database_status
         , readiness_status         = p_row.readiness_status
         , enabled                  = p_row.enabled
         , last_error_code          = p_row.last_error_code
         , last_error_message       = p_row.last_error_message
     where plugin_registry_id = p_plugin_registry_id
    returning row_version into p_row.row_version;
  end upd;
end plugin_registry_tapi;
/
--rollback drop package body orac_api.plugin_registry_tapi
