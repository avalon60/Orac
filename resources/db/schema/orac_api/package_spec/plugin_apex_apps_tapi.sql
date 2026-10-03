--liquibase formatted sql

--changeset clive:plugin_apex_apps_tapi_create_spec stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package orac_api.plugin_apex_apps_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.plugin_apex_apps_v%rowtype
  );

  procedure upd(
    p_plugin_apex_app_id in     orac_api.plugin_apex_apps_v.plugin_apex_app_id%type,
    p_row                in out orac_api.plugin_apex_apps_v%rowtype
  );
  procedure delete_for_removal(p_removal_id in varchar2);
  procedure record_installation_receipt(
    p_plugin_id in varchar2,
    p_app_alias in varchar2,
    p_installed_app_id in number,
    p_receipt in json
  );
end plugin_apex_apps_tapi;
/
--rollback drop package orac_api.plugin_apex_apps_tapi;
