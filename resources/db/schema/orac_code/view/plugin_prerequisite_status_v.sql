--liquibase formatted sql

--changeset clive:create_view_orac_code_plugin_prerequisite_status_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.plugin_prerequisite_status_v as
select plugin_id,
       command_prerequisite_status,
       case command_prerequisite_status
         when 'success' then 'Pandoc document conversion is available.'
         when 'degraded' then 'Pandoc is unavailable or incompatible; Markdown and plain text remain available.'
         when 'failed' then 'A required command prerequisite is unavailable.'
         else 'This plugin has no command prerequisites.'
       end capability_message,
       command_dependency_report
  from orac_api.plugin_registry_v;
--rollback drop view orac_code.plugin_prerequisite_status_v;
