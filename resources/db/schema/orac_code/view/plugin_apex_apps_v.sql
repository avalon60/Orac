--liquibase formatted sql

--changeset clive:create_view_orac_code_view_plugin_apex_apps_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: approved runtime projection of plugin APEX app registry state

create or replace view orac_code.plugin_apex_apps_v as
select plugin_id
     , plugin_version
     , app_alias
     , workspace
     , parsing_schema
     , app_export
     , declared_application_id
     , installed_app_id
     , entry_page_id
     , label
     , description
     , required_roles
     , icon
     , card_title
     , card_subtitle
     , install_status
     , last_error_message
     , enabled
     , row_version
  from orac_api.plugin_apex_apps_v;

--rollback drop view orac_code.plugin_apex_apps_v;
