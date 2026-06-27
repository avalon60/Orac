--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_plugin_apex_app_admin_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-23
-- __description__: controlled plugin APEX application administration API body

create or replace package body orac_code.plugin_apex_app_admin_api as
  procedure set_enabled(
    p_plugin_id    in orac_api.plugin_apex_apps_v.plugin_id%type,
    p_app_alias    in orac_api.plugin_apex_apps_v.app_alias%type,
    p_enabled      in orac_api.plugin_apex_apps_v.enabled%type,
    p_row_version  in orac_api.plugin_apex_apps_v.row_version%type
  )
  is
    l_row orac_api.plugin_apex_apps_v%rowtype;
  begin
    if upper(p_enabled) not in ('Y', 'N')
    then
      raise_application_error(
        -20000,
        'Plugin APEX app enabled value must be Y or N.'
      );
    end if;

    begin
      select *
        into l_row
        from orac_api.plugin_apex_apps_v
       where plugin_id = p_plugin_id
         and app_alias = p_app_alias
         and row_version = p_row_version;
    exception
      when no_data_found then
        raise_application_error(
          -20001,
          'Plugin APEX app was changed by another session. Refresh and try again.'
        );
    end;

    l_row.enabled := upper(p_enabled);

    orac_api.plugin_apex_apps_tapi.upd(
      p_plugin_apex_app_id => l_row.plugin_apex_app_id,
      p_row                => l_row
    );
  end set_enabled;
end plugin_apex_app_admin_api;
/

--rollback drop package body orac_code.plugin_apex_app_admin_api;
