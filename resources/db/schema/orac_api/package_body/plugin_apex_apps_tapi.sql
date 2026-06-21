--liquibase formatted sql

--changeset clive:plugin_apex_apps_tapi_create_body stripComments:false endDelimiter:/ runOnChange:true

create or replace package body orac_api.plugin_apex_apps_tapi
as
  procedure ins(
    p_row in out orac_api.plugin_apex_apps_v%rowtype
  )
  is
  begin
    insert into orac_api.plugin_apex_apps_v
      (
        plugin_id, plugin_version, app_alias, workspace, parsing_schema,
        app_export, declared_application_id, installed_app_id, entry_page_id,
        label, description, required_roles, icon, card_title, card_subtitle,
        install_status, install_log, last_error_message, enabled
      )
    values
      (
        p_row.plugin_id, p_row.plugin_version, p_row.app_alias,
        p_row.workspace, p_row.parsing_schema, p_row.app_export,
        p_row.declared_application_id, p_row.installed_app_id,
        p_row.entry_page_id, p_row.label, p_row.description,
        p_row.required_roles, p_row.icon, p_row.card_title,
        p_row.card_subtitle, p_row.install_status, p_row.install_log,
        p_row.last_error_message, p_row.enabled
      )
    returning plugin_apex_app_id, row_version
         into p_row.plugin_apex_app_id, p_row.row_version;
  end ins;

  procedure upd(
    p_plugin_apex_app_id in     orac_api.plugin_apex_apps_v.plugin_apex_app_id%type,
    p_row                in out orac_api.plugin_apex_apps_v%rowtype
  )
  is
  begin
    update orac_api.plugin_apex_apps_v
       set plugin_version          = p_row.plugin_version
         , workspace               = p_row.workspace
         , parsing_schema          = p_row.parsing_schema
         , app_export              = p_row.app_export
         , declared_application_id = p_row.declared_application_id
         , installed_app_id        = p_row.installed_app_id
         , entry_page_id           = p_row.entry_page_id
         , label                   = p_row.label
         , description             = p_row.description
         , required_roles          = p_row.required_roles
         , icon                    = p_row.icon
         , card_title              = p_row.card_title
         , card_subtitle           = p_row.card_subtitle
         , install_status          = p_row.install_status
         , install_log             = p_row.install_log
         , last_error_message      = p_row.last_error_message
         , enabled                 = p_row.enabled
     where plugin_apex_app_id = p_plugin_apex_app_id
    returning row_version into p_row.row_version;
  end upd;
end plugin_apex_apps_tapi;
/
--rollback drop package body orac_api.plugin_apex_apps_tapi
