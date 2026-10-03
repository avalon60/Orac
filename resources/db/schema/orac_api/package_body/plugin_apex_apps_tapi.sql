--liquibase formatted sql

--changeset clive:plugin_apex_apps_tapi_create_body stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

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
  procedure record_installation_receipt(
    p_plugin_id in varchar2,
    p_app_alias in varchar2,
    p_installed_app_id in number,
    p_receipt in json
  ) is
    l_count number;
  begin
    if sys_context('userenv', 'session_user') <> 'SYS' then
      raise_application_error(-20078, 'APEX ownership requires privileged host installation.');
    end if;
    select count(*) into l_count from orac_api.plugin_registry_v plugin
     where plugin.plugin_id = p_plugin_id
       and plugin.plugin_registry_id = json_value(p_receipt, '$.plugin_registry_id' returning number)
       and p_installed_app_id = json_value(p_receipt, '$.application_id' returning number)
       and json_value(p_receipt, '$.database_identity') is not null
       and regexp_like(json_value(p_receipt, '$.marker'), '^[A-Fa-f0-9]{32}$')
       and not exists (select 1 from orac_api.plugin_removals_v removal
                        where removal.plugin_registry_id = plugin.plugin_registry_id
                          and removal.completed_on is null);
    if l_count <> 1 then
      raise_application_error(-20079, 'APEX receipt does not match the current registration.');
    end if;
    update orac_api.plugin_apex_apps_v
       set installed_app_id = p_installed_app_id, installation_receipt = p_receipt
     where plugin_id = p_plugin_id and app_alias = p_app_alias;
    if sql%rowcount <> 1 then
      raise_application_error(-20079, 'APEX metadata must be reserved before import.');
    end if;
  end record_installation_receipt;

  procedure delete_for_removal(p_removal_id in varchar2) is
    l_removal orac_api.plugin_removals_v%rowtype;
  begin
    select * into l_removal from orac_api.plugin_removals_v
     where removal_id = p_removal_id and completed_on is null
       and external_complete_yn = 'Y' and files_complete_yn = 'Y';
    delete from orac_api.plugin_apex_apps_v
     where plugin_id = l_removal.plugin_id;
  end delete_for_removal;
end plugin_apex_apps_tapi;
/
--rollback drop package body orac_api.plugin_apex_apps_tapi
