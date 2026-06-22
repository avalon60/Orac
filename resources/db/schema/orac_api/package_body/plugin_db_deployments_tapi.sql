--liquibase formatted sql

--changeset clive:plugin_db_deployments_tapi_create_body stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package body orac_api.plugin_db_deployments_tapi
as
  procedure ins(
    p_row in out orac_api.plugin_db_deployments_v%rowtype
  )
  is
  begin
    insert into orac_api.plugin_db_deployments_v
      (
        plugin_id
      , plugin_version
      , schema_name
      , deployment_checksum
      , deployment_status
      , started_on
      , completed_on
      , error_message
      , log_path
      )
    values
      (
        p_row.plugin_id
      , p_row.plugin_version
      , p_row.schema_name
      , p_row.deployment_checksum
      , p_row.deployment_status
      , nvl(p_row.started_on, systimestamp)
      , p_row.completed_on
      , p_row.error_message
      , p_row.log_path
      )
    returning
        plugin_db_deployment_id
      , row_version
      into
        p_row.plugin_db_deployment_id
      , p_row.row_version;
  end ins;

  procedure get(
    p_plugin_db_deployment_id in  orac_api.plugin_db_deployments_v.plugin_db_deployment_id%type,
    p_row                     out orac_api.plugin_db_deployments_v%rowtype
  )
  is
  begin
    select
        plugin_db_deployment_id
      , plugin_id
      , plugin_version
      , schema_name
      , deployment_checksum
      , deployment_status
      , started_on
      , completed_on
      , error_message
      , log_path
      , created_on
      , created_by
      , updated_on
      , updated_by
      , row_version
      into
        p_row.plugin_db_deployment_id
      , p_row.plugin_id
      , p_row.plugin_version
      , p_row.schema_name
      , p_row.deployment_checksum
      , p_row.deployment_status
      , p_row.started_on
      , p_row.completed_on
      , p_row.error_message
      , p_row.log_path
      , p_row.created_on
      , p_row.created_by
      , p_row.updated_on
      , p_row.updated_by
      , p_row.row_version
      from orac_api.plugin_db_deployments_v
     where plugin_db_deployment_id = p_plugin_db_deployment_id;
  end get;

  procedure upd(
    p_plugin_db_deployment_id in     orac_api.plugin_db_deployments_v.plugin_db_deployment_id%type,
    p_row                     in out orac_api.plugin_db_deployments_v%rowtype
  )
  is
  begin
    update orac_api.plugin_db_deployments_v
       set plugin_id           = p_row.plugin_id
         , plugin_version      = p_row.plugin_version
         , schema_name         = p_row.schema_name
         , deployment_checksum = p_row.deployment_checksum
         , deployment_status   = p_row.deployment_status
         , started_on          = p_row.started_on
         , completed_on        = p_row.completed_on
         , error_message       = p_row.error_message
         , log_path            = p_row.log_path
     where plugin_db_deployment_id = p_plugin_db_deployment_id
    returning row_version
         into p_row.row_version;
  end upd;
end plugin_db_deployments_tapi;
/
--rollback drop package body orac_api.plugin_db_deployments_tapi
