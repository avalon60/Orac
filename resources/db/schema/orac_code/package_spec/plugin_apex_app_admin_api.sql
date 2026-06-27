--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_plugin_apex_app_admin_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-23
-- __description__: controlled plugin APEX application administration API

create or replace package orac_code.plugin_apex_app_admin_api as
  procedure set_enabled(
    p_plugin_id    in orac_api.plugin_apex_apps_v.plugin_id%type,
    p_app_alias    in orac_api.plugin_apex_apps_v.app_alias%type,
    p_enabled      in orac_api.plugin_apex_apps_v.enabled%type,
    p_row_version  in orac_api.plugin_apex_apps_v.row_version%type
  );
end plugin_apex_app_admin_api;
/

--rollback drop package orac_code.plugin_apex_app_admin_api;
