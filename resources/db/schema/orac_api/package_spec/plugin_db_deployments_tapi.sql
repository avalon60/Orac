--liquibase formatted sql

--changeset clive:plugin_db_deployments_tapi_create_spec stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package orac_api.plugin_db_deployments_tapi
authid definer
as
  subtype ty_row is orac_api.plugin_db_deployments_v%rowtype;

  procedure ins(
    p_row in out orac_api.plugin_db_deployments_v%rowtype
  );

  procedure get(
    p_plugin_db_deployment_id in  orac_api.plugin_db_deployments_v.plugin_db_deployment_id%type,
    p_row                     out orac_api.plugin_db_deployments_v%rowtype
  );

  procedure upd(
    p_plugin_db_deployment_id in     orac_api.plugin_db_deployments_v.plugin_db_deployment_id%type,
    p_row                     in out orac_api.plugin_db_deployments_v%rowtype
  );
end plugin_db_deployments_tapi;
/
--rollback drop package orac_api.plugin_db_deployments_tapi;