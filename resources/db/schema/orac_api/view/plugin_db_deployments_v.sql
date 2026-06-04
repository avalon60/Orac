--liquibase formatted sql

--changeset clive:plugin_db_deployments_v_create stripComments:false runOnChange:true

create or replace force view orac_api.plugin_db_deployments_v as
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
     from orac_core.plugin_db_deployments;
--rollback drop view orac_api.plugin_db_deployments_v;
