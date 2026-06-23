--liquibase formatted sql

--changeset clive:plugin_audit_events_tapi_create_body stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package body orac_api.plugin_audit_events_tapi
as
  procedure ins(
    p_row in out orac_api.plugin_audit_events_v%rowtype
  )
  is
  begin
    insert into orac_api.plugin_audit_events_v
      (
        plugin_invocation_id
      , event_type
      , event_status
      , event_message
      , policy_decision
      , confirmation_id
      , execution_status
      , failure_type
      , failure_message
      , event_payload_json
      )
    values
      (
        p_row.plugin_invocation_id
      , p_row.event_type
      , p_row.event_status
      , p_row.event_message
      , p_row.policy_decision
      , p_row.confirmation_id
      , p_row.execution_status
      , p_row.failure_type
      , p_row.failure_message
      , p_row.event_payload_json
      )
    returning
        plugin_audit_event_id
      , row_version
      into
        p_row.plugin_audit_event_id
      , p_row.row_version;
  end ins;

  procedure get(
    p_plugin_audit_event_id in  orac_api.plugin_audit_events_v.plugin_audit_event_id%type,
    p_row                   out orac_api.plugin_audit_events_v%rowtype
  )
  is
  begin
    select
        plugin_audit_event_id
      , plugin_invocation_id
      , event_type
      , event_status
      , event_message
      , policy_decision
      , confirmation_id
      , execution_status
      , failure_type
      , failure_message
      , event_payload_json
      , created_on
      , created_by
      , updated_on
      , updated_by
      , row_version
      into
        p_row.plugin_audit_event_id
      , p_row.plugin_invocation_id
      , p_row.event_type
      , p_row.event_status
      , p_row.event_message
      , p_row.policy_decision
      , p_row.confirmation_id
      , p_row.execution_status
      , p_row.failure_type
      , p_row.failure_message
      , p_row.event_payload_json
      , p_row.created_on
      , p_row.created_by
      , p_row.updated_on
      , p_row.updated_by
      , p_row.row_version
      from orac_api.plugin_audit_events_v
     where plugin_audit_event_id = p_plugin_audit_event_id;
  end get;
end plugin_audit_events_tapi;
/
--rollback drop package body orac_api.plugin_audit_events_tapi
