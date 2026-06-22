--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_plugin_audit_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: ORAC_CODE API for durable plugin audit/result persistence

create or replace package orac_code.plugin_audit_api as
  procedure begin_invocation(
    p_plugin_invocation_id out orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type,
    p_plugin_id            in  orac_api.plugin_invocations_v.plugin_id%type,
    p_plugin_name          in  orac_api.plugin_invocations_v.plugin_name%type,
    p_action_type          in  orac_api.plugin_invocations_v.action_type%type,
    p_request_id           in  orac_api.plugin_invocations_v.request_id%type default null,
    p_correlation_id       in  orac_api.plugin_invocations_v.correlation_id%type default null,
    p_turn_id              in  orac_api.plugin_invocations_v.turn_id%type default null,
    p_conversation_id      in  orac_api.plugin_invocations_v.conversation_id%type default null,
    p_message_id           in  orac_api.plugin_invocations_v.message_id%type default null,
    p_user_id              in  orac_api.plugin_invocations_v.user_id%type default null,
    p_capabilities         in  orac_api.plugin_invocations_v.capabilities%type default null,
    p_entitlements         in  orac_api.plugin_invocations_v.entitlements%type default null,
    p_provenance_json      in  orac_api.plugin_invocations_v.provenance_json%type default null
  );

  procedure record_policy_decision(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_policy_decision      in  orac_api.plugin_invocations_v.policy_decision%type,
    p_policy_reason        in  orac_api.plugin_invocations_v.policy_reason%type default null,
    p_event_message        in  orac_api.plugin_audit_events_v.event_message%type default null,
    p_provenance_json      in  orac_api.plugin_invocations_v.provenance_json%type default null,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type
  );

  procedure record_confirmation_event(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_event_type           in  orac_api.plugin_audit_events_v.event_type%type,
    p_confirmation_id      in  orac_api.plugin_invocations_v.confirmation_id%type,
    p_confirmation_status  in  orac_api.plugin_invocations_v.confirmation_status%type,
    p_event_message        in  orac_api.plugin_audit_events_v.event_message%type default null,
    p_event_payload_json   in  orac_api.plugin_audit_events_v.event_payload_json%type default null,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type
  );

  procedure record_execution_event(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_event_type           in  orac_api.plugin_audit_events_v.event_type%type,
    p_execution_status     in  orac_api.plugin_invocations_v.execution_status%type,
    p_timeout_seconds      in  orac_api.plugin_invocations_v.timeout_seconds%type default null,
    p_failure_type         in  orac_api.plugin_invocations_v.failure_type%type default null,
    p_failure_message      in  orac_api.plugin_invocations_v.failure_message%type default null,
    p_provenance_json      in  orac_api.plugin_invocations_v.provenance_json%type default null,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type
  );

  procedure link_message(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_message_id           in  orac_api.plugin_invocations_v.message_id%type,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type
  );
end plugin_audit_api;
/

--rollback drop package orac_code.plugin_audit_api;
