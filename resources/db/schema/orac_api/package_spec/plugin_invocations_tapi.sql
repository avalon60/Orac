--liquibase formatted sql

--changeset clive:plugin_invocations_tapi_create_spec stripComments:false endDelimiter:/ runOnChange:true

create or replace package orac_api.plugin_invocations_tapi
authid definer
as
  subtype ty_row is orac_api.plugin_invocations_v%rowtype;

  procedure ins(
    p_row in out orac_api.plugin_invocations_v%rowtype
  );

  procedure get(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_row                  out orac_api.plugin_invocations_v%rowtype
  );

  procedure upd(
    p_plugin_invocation_id in     orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_row                  in out orac_api.plugin_invocations_v%rowtype
  );
end plugin_invocations_tapi;
/
--rollback drop package orac_api.plugin_invocations_tapi
