--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_plugin_apex_app_registry_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: controlled plugin APEX application registry API body

create or replace package body orac_code.plugin_apex_app_registry_api as
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
  )
  is
    l_row orac_api.plugin_apex_apps_v%rowtype;
  begin
    begin
      select *
        into l_row
        from orac_api.plugin_apex_apps_v
       where plugin_id = p_plugin_id
         and app_alias = p_app_alias;
    exception
      when no_data_found then
        null;
    end;

    l_row.plugin_id := p_plugin_id;
    l_row.plugin_version := p_plugin_version;
    l_row.app_alias := p_app_alias;
    l_row.workspace := p_workspace;
    l_row.parsing_schema := p_parsing_schema;
    l_row.app_export := p_app_export;
    l_row.declared_application_id := p_declared_application_id;
    l_row.installed_app_id := p_installed_app_id;
    l_row.entry_page_id := p_entry_page_id;
    l_row.label := p_label;
    l_row.description := p_description;
    l_row.required_roles := p_required_roles;
    l_row.icon := p_icon;
    l_row.card_title := p_card_title;
    l_row.card_subtitle := p_card_subtitle;
    l_row.install_status := p_install_status;
    l_row.install_log := p_install_log;
    l_row.last_error_message := p_last_error_message;
    l_row.enabled := p_enabled;

    if l_row.plugin_apex_app_id is null
    then
      orac_api.plugin_apex_apps_tapi.ins(l_row);
    else
      orac_api.plugin_apex_apps_tapi.upd(l_row.plugin_apex_app_id, l_row);
    end if;
  end upsert_app;
end plugin_apex_app_registry_api;
/

--rollback drop package body orac_code.plugin_apex_app_registry_api;
