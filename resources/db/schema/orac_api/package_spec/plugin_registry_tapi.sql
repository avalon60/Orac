--liquibase formatted sql

--changeset clive:plugin_registry_tapi_create_spec stripComments:false endDelimiter:/ runOnChange:true

create or replace package orac_api.plugin_registry_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.plugin_registry_v%rowtype
  );

  procedure upd(
    p_plugin_registry_id in     orac_api.plugin_registry_v.plugin_registry_id%type,
    p_row                in out orac_api.plugin_registry_v%rowtype
  );
end plugin_registry_tapi;
/
--rollback drop package orac_api.plugin_registry_tapi
