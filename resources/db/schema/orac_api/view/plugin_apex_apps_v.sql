--liquibase formatted sql

--changeset clive:plugin_apex_apps_v_create stripComments:false runOnChange:true

create or replace force view orac_api.plugin_apex_apps_v as
select plugin_apex_app_id
     , plugin_id
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
     , install_log
     , last_error_message
     , enabled
     , created_on
     , created_by
     , updated_on
     , updated_by
     , row_version
  from orac_core.plugin_apex_apps;
--rollback drop view orac_api.plugin_apex_apps_v;
