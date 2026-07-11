--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_plugin_registry_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-07
-- __description__: controlled plugin installation registry API

create or replace package orac_code.plugin_registry_api as
  procedure upsert_plugin(
    p_plugin_id                in orac_api.plugin_registry_v.plugin_id%type,
    p_plugin_name              in orac_api.plugin_registry_v.plugin_name%type,
    p_plugin_version           in orac_api.plugin_registry_v.plugin_version%type,
    p_runtime_mode             in orac_api.plugin_registry_v.runtime_mode%type,
    p_manifest_hash            in orac_api.plugin_registry_v.manifest_hash%type,
    p_package_hash             in orac_api.plugin_registry_v.package_hash%type,
    p_install_source_type      in orac_api.plugin_registry_v.install_source_type%type,
    p_install_source_ref       in orac_api.plugin_registry_v.install_source_ref%type,
    p_installed_path           in orac_api.plugin_registry_v.installed_path%type,
    p_config_path              in orac_api.plugin_registry_v.config_path%type,
    p_capabilities_summary     in orac_api.plugin_registry_v.capabilities_summary%type,
    p_entitlements_summary     in orac_api.plugin_registry_v.entitlements_summary%type,
    p_database_schemas_summary in orac_api.plugin_registry_v.database_schemas_summary%type,
    p_dependency_declarations  in orac_api.plugin_registry_v.dependency_declarations%type,
    p_dependency_fingerprint   in orac_api.plugin_registry_v.dependency_fingerprint%type,
    p_install_status           in orac_api.plugin_registry_v.install_status%type,
    p_configuration_status     in orac_api.plugin_registry_v.configuration_status%type,
    p_dependency_status        in orac_api.plugin_registry_v.dependency_status%type,
    p_database_status          in orac_api.plugin_registry_v.database_status%type,
    p_readiness_status         in orac_api.plugin_registry_v.readiness_status%type,
    p_enabled                  in orac_api.plugin_registry_v.enabled%type,
    p_ui_icon_class            in orac_api.plugin_registry_v.ui_icon_class%type default null,
    p_ui_accent_class          in orac_api.plugin_registry_v.ui_accent_class%type default null,
    p_last_error_code          in orac_api.plugin_registry_v.last_error_code%type default null,
    p_last_error_message       in orac_api.plugin_registry_v.last_error_message%type default null
  );
end plugin_registry_api;
/

--rollback drop package orac_code.plugin_registry_api;
