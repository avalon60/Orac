--liquibase formatted sql

--changeset clive:plugin_audit_events_tapi_create_spec stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package orac_api.plugin_audit_events_tapi
authid definer
as
  subtype ty_row is orac_api.plugin_audit_events_v%rowtype;

  procedure ins(
    p_row in out orac_api.plugin_audit_events_v%rowtype
  );

  procedure get(
    p_plugin_audit_event_id in  orac_api.plugin_audit_events_v.plugin_audit_event_id%type,
    p_row                   out orac_api.plugin_audit_events_v%rowtype
  );
end plugin_audit_events_tapi;
/
--rollback drop package orac_api.plugin_audit_events_tapi;