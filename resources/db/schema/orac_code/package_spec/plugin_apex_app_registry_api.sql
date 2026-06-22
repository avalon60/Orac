--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_plugin_apex_app_registry_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: controlled plugin APEX application registry API

create or replace package orac_code.plugin_apex_app_registry_api as
  procedure upsert_app(
    p_plugin_id               in orac_api.plugin_apex_apps_v.plugin_id%type,
    p_plugin_version          in orac_api.plugin_apex_apps_v.plugin_version%type,
    p_app_alias               in orac_api.plugin_apex_apps_v.app_alias%type,
    p_workspace               in orac_api.plugin_apex_apps_v.workspace%type,
    p_parsing_schema          in orac_api.plugin_apex_apps_v.parsing_schema%type,
    p_app_export              in orac_api.plugin_apex_apps_v.app_export%type,
    p_declared_application_id in orac_api.plugin_apex_apps_v.declared_application_id%type,
    p_installed_app_id        in orac_api.plugin_apex_apps_v.installed_app_id%type,
    p_entry_page_id           in orac_api.plugin_apex_apps_v.entry_page_id%type,
    p_label                   in orac_api.plugin_apex_apps_v.label%type,
    p_description             in orac_api.plugin_apex_apps_v.description%type,
    p_required_roles          in orac_api.plugin_apex_apps_v.required_roles%type,
    p_icon                    in orac_api.plugin_apex_apps_v.icon%type,
    p_card_title              in orac_api.plugin_apex_apps_v.card_title%type,
    p_card_subtitle           in orac_api.plugin_apex_apps_v.card_subtitle%type,
    p_install_status          in orac_api.plugin_apex_apps_v.install_status%type,
    p_install_log             in orac_api.plugin_apex_apps_v.install_log%type,
    p_last_error_message      in orac_api.plugin_apex_apps_v.last_error_message%type,
    p_enabled                 in orac_api.plugin_apex_apps_v.enabled%type
  );
end plugin_apex_app_registry_api;
/

--rollback drop package orac_code.plugin_apex_app_registry_api;
