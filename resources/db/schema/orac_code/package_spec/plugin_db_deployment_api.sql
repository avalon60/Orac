--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_plugin_db_deployment_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-03
-- __description__: ORAC_CODE API for plugin database deployment state

create or replace package orac_code.plugin_db_deployment_api as
  procedure record_status(
    p_plugin_id           in  orac_api.plugin_db_deployments_v.plugin_id%type,
    p_plugin_version      in  orac_api.plugin_db_deployments_v.plugin_version%type,
    p_schema_name         in  orac_api.plugin_db_deployments_v.schema_name%type,
    p_deployment_checksum in  orac_api.plugin_db_deployments_v.deployment_checksum%type,
    p_deployment_status   in  orac_api.plugin_db_deployments_v.deployment_status%type,
    p_error_message       in  orac_api.plugin_db_deployments_v.error_message%type default null,
    p_log_path            in  orac_api.plugin_db_deployments_v.log_path%type default null,
    p_row_version         out orac_api.plugin_db_deployments_v.row_version%type
  );

  function is_deployed(
    p_plugin_id           in  orac_api.plugin_db_deployments_v.plugin_id%type,
    p_plugin_version      in  orac_api.plugin_db_deployments_v.plugin_version%type,
    p_schema_name         in  orac_api.plugin_db_deployments_v.schema_name%type,
    p_deployment_checksum in  orac_api.plugin_db_deployments_v.deployment_checksum%type
  ) return varchar2;
end plugin_db_deployment_api;
/

--rollback drop package orac_code.plugin_db_deployment_api;
