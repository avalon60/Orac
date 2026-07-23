--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_plugin_registry_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-07
-- __description__: controlled plugin installation registry API body

create or replace package body orac_code.plugin_registry_api as
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
  )
  is
    l_row orac_api.plugin_registry_v%rowtype;
  begin
    begin
      select *
        into l_row
        from orac_api.plugin_registry_v
       where plugin_id = p_plugin_id;
    exception
      when no_data_found then
        null;
    end;

    l_row.plugin_id := p_plugin_id;
    l_row.plugin_name := p_plugin_name;
    l_row.plugin_version := p_plugin_version;
    l_row.runtime_mode := p_runtime_mode;
    l_row.manifest_hash := p_manifest_hash;
    l_row.package_hash := p_package_hash;
    l_row.install_source_type := p_install_source_type;
    l_row.install_source_ref := p_install_source_ref;
    l_row.installed_path := p_installed_path;
    l_row.config_path := p_config_path;
    l_row.capabilities_summary := p_capabilities_summary;
    l_row.entitlements_summary := p_entitlements_summary;
    l_row.database_schemas_summary := p_database_schemas_summary;
    l_row.ui_icon_class := p_ui_icon_class;
    l_row.ui_accent_class := p_ui_accent_class;
    l_row.dependency_declarations := p_dependency_declarations;
    l_row.dependency_fingerprint := p_dependency_fingerprint;
    l_row.install_status := p_install_status;
    l_row.configuration_status := p_configuration_status;
    l_row.dependency_status := p_dependency_status;
    l_row.database_status := p_database_status;
    l_row.readiness_status := p_readiness_status;
    l_row.enabled := p_enabled;
    l_row.last_error_code := p_last_error_code;
    l_row.last_error_message := p_last_error_message;

    if l_row.plugin_registry_id is null
    then
      orac_api.plugin_registry_tapi.ins(l_row);
    else
      orac_api.plugin_registry_tapi.upd(l_row.plugin_registry_id, l_row);
    end if;
    orac_code.knowledge_scope_api.synchronise_plugin_scope(
      l_row.plugin_registry_id
    );
  end upsert_plugin;
end plugin_registry_api;
/

--rollback drop package body orac_code.plugin_registry_api;
