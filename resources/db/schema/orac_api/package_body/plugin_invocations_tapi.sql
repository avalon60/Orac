--liquibase formatted sql

--changeset clive:plugin_invocations_tapi_create_body stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package body orac_api.plugin_invocations_tapi
as
  procedure ins(
    p_row in out orac_api.plugin_invocations_v%rowtype
  )
  is
  begin
    insert into orac_api.plugin_invocations_v
      (
        request_id
      , correlation_id
      , turn_id
      , conversation_id
      , message_id
      , user_id
      , plugin_id
      , plugin_name
      , action_type
      , capabilities
      , entitlements
      , policy_decision
      , policy_reason
      , confirmation_id
      , confirmation_status
      , execution_status
      , timeout_seconds
      , failure_type
      , failure_message
      , provenance_json
      )
    values
      (
        p_row.request_id
      , p_row.correlation_id
      , p_row.turn_id
      , p_row.conversation_id
      , p_row.message_id
      , p_row.user_id
      , p_row.plugin_id
      , p_row.plugin_name
      , p_row.action_type
      , p_row.capabilities
      , p_row.entitlements
      , p_row.policy_decision
      , p_row.policy_reason
      , p_row.confirmation_id
      , p_row.confirmation_status
      , p_row.execution_status
      , p_row.timeout_seconds
      , p_row.failure_type
      , p_row.failure_message
      , p_row.provenance_json
      )
    returning
        plugin_invocation_id
      , row_version
      into
        p_row.plugin_invocation_id
      , p_row.row_version;
  end ins;

  procedure get(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_row                  out orac_api.plugin_invocations_v%rowtype
  )
  is
  begin
    select
        plugin_invocation_id
      , request_id
      , correlation_id
      , turn_id
      , conversation_id
      , message_id
      , user_id
      , plugin_id
      , plugin_name
      , action_type
      , capabilities
      , entitlements
      , policy_decision
      , policy_reason
      , confirmation_id
      , confirmation_status
      , execution_status
      , timeout_seconds
      , failure_type
      , failure_message
      , provenance_json
      , created_on
      , created_by
      , updated_on
      , updated_by
      , row_version
      into
        p_row.plugin_invocation_id
      , p_row.request_id
      , p_row.correlation_id
      , p_row.turn_id
      , p_row.conversation_id
      , p_row.message_id
      , p_row.user_id
      , p_row.plugin_id
      , p_row.plugin_name
      , p_row.action_type
      , p_row.capabilities
      , p_row.entitlements
      , p_row.policy_decision
      , p_row.policy_reason
      , p_row.confirmation_id
      , p_row.confirmation_status
      , p_row.execution_status
      , p_row.timeout_seconds
      , p_row.failure_type
      , p_row.failure_message
      , p_row.provenance_json
      , p_row.created_on
      , p_row.created_by
      , p_row.updated_on
      , p_row.updated_by
      , p_row.row_version
      from orac_api.plugin_invocations_v
     where plugin_invocation_id = p_plugin_invocation_id;
  end get;

  procedure upd(
    p_plugin_invocation_id in     orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_row                  in out orac_api.plugin_invocations_v%rowtype
  )
  is
  begin
    update orac_api.plugin_invocations_v
       set request_id          = p_row.request_id
         , correlation_id      = p_row.correlation_id
         , turn_id             = p_row.turn_id
         , conversation_id     = p_row.conversation_id
         , message_id          = p_row.message_id
         , user_id             = p_row.user_id
         , plugin_id           = p_row.plugin_id
         , plugin_name         = p_row.plugin_name
         , action_type         = p_row.action_type
         , capabilities        = p_row.capabilities
         , entitlements        = p_row.entitlements
         , policy_decision     = p_row.policy_decision
         , policy_reason       = p_row.policy_reason
         , confirmation_id     = p_row.confirmation_id
         , confirmation_status = p_row.confirmation_status
         , execution_status    = p_row.execution_status
         , timeout_seconds     = p_row.timeout_seconds
         , failure_type        = p_row.failure_type
         , failure_message     = p_row.failure_message
         , provenance_json     = p_row.provenance_json
     where plugin_invocation_id = p_plugin_invocation_id
    returning
        plugin_invocation_id
      , row_version
      into
        p_row.plugin_invocation_id
      , p_row.row_version;
  end upd;
end plugin_invocations_tapi;
/
--rollback drop package body orac_api.plugin_invocations_tapi
