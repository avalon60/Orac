-- __author__: clive
-- __date__: 2026-05-25
-- __description__: ORAC_CODE API body for durable plugin audit/result persistence

create or replace package body orac_code.plugin_audit_api as
  procedure add_event(
    p_plugin_invocation_id in orac_api.plugin_audit_events_v.plugin_invocation_id%type,
    p_event_type           in orac_api.plugin_audit_events_v.event_type%type,
    p_event_status         in orac_api.plugin_audit_events_v.event_status%type default null,
    p_event_message        in orac_api.plugin_audit_events_v.event_message%type default null,
    p_policy_decision      in orac_api.plugin_audit_events_v.policy_decision%type default null,
    p_confirmation_id      in orac_api.plugin_audit_events_v.confirmation_id%type default null,
    p_execution_status     in orac_api.plugin_audit_events_v.execution_status%type default null,
    p_failure_type         in orac_api.plugin_audit_events_v.failure_type%type default null,
    p_failure_message      in orac_api.plugin_audit_events_v.failure_message%type default null,
    p_event_payload_json   in orac_api.plugin_audit_events_v.event_payload_json%type default null
  ) as
    l_event_row orac_api.plugin_audit_events_v%rowtype;
  begin
    l_event_row.plugin_invocation_id := p_plugin_invocation_id;
    l_event_row.event_type := p_event_type;
    l_event_row.event_status := p_event_status;
    l_event_row.event_message := p_event_message;
    l_event_row.policy_decision := p_policy_decision;
    l_event_row.confirmation_id := p_confirmation_id;
    l_event_row.execution_status := p_execution_status;
    l_event_row.failure_type := p_failure_type;
    l_event_row.failure_message := p_failure_message;
    l_event_row.event_payload_json := p_event_payload_json;

    orac_api.plugin_audit_events_tapi.ins(l_event_row);
  end add_event;

  function policy_execution_status(
    p_policy_decision in orac_api.plugin_invocations_v.policy_decision%type
  ) return orac_api.plugin_invocations_v.execution_status%type
  as
  begin
    if p_policy_decision = 'denied' then
      return 'denied';
    elsif p_policy_decision = 'requires_confirmation' then
      return 'confirmation_required';
    end if;

    return 'policy_evaluated';
  end policy_execution_status;

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
  ) as
    l_row orac_api.plugin_invocations_v%rowtype;
  begin
    l_row.request_id := p_request_id;
    l_row.correlation_id := p_correlation_id;
    l_row.turn_id := p_turn_id;
    l_row.conversation_id := p_conversation_id;
    l_row.message_id := p_message_id;
    l_row.user_id := p_user_id;
    l_row.plugin_id := p_plugin_id;
    l_row.plugin_name := p_plugin_name;
    l_row.action_type := p_action_type;
    l_row.capabilities := p_capabilities;
    l_row.entitlements := p_entitlements;
    l_row.execution_status := 'candidate_selected';
    l_row.provenance_json := p_provenance_json;

    orac_api.plugin_invocations_tapi.ins(l_row);
    p_plugin_invocation_id := l_row.plugin_invocation_id;
    p_row_version := l_row.row_version;

    add_event(
      p_plugin_invocation_id => l_row.plugin_invocation_id,
      p_event_type           => 'candidate_selected',
      p_execution_status     => 'candidate_selected',
      p_event_payload_json   => p_provenance_json
    );
  end begin_invocation;

  procedure record_policy_decision(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_policy_decision      in  orac_api.plugin_invocations_v.policy_decision%type,
    p_policy_reason        in  orac_api.plugin_invocations_v.policy_reason%type default null,
    p_event_message        in  orac_api.plugin_audit_events_v.event_message%type default null,
    p_provenance_json      in  orac_api.plugin_invocations_v.provenance_json%type default null,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type
  ) as
    l_row              orac_api.plugin_invocations_v%rowtype;
    l_execution_status orac_api.plugin_invocations_v.execution_status%type;
    l_event_type       orac_api.plugin_audit_events_v.event_type%type;
  begin
    orac_api.plugin_invocations_tapi.get(p_plugin_invocation_id, l_row);
    l_execution_status := policy_execution_status(p_policy_decision);

    if l_execution_status = 'confirmation_required' then
      l_event_type := 'confirmation_required';
    else
      l_event_type := 'policy_evaluated';
    end if;

    l_row.policy_decision := p_policy_decision;
    l_row.policy_reason := p_policy_reason;
    l_row.execution_status := l_execution_status;

    -- Invocation provenance is captured by begin_invocation. Reassigning a
    -- JSON formal during an update crashes Oracle 23.26 in kohfrem(). The
    -- current provenance remains preserved on the event row below.

    orac_api.plugin_invocations_tapi.upd(p_plugin_invocation_id, l_row);
    p_row_version := l_row.row_version;

    add_event(
      p_plugin_invocation_id => p_plugin_invocation_id,
      p_event_type           => l_event_type,
      p_event_message        => coalesce(p_event_message, p_policy_reason),
      p_policy_decision      => p_policy_decision,
      p_execution_status     => l_execution_status,
      p_event_payload_json   => p_provenance_json
    );
  end record_policy_decision;

  procedure record_confirmation_event(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_event_type           in  orac_api.plugin_audit_events_v.event_type%type,
    p_confirmation_id      in  orac_api.plugin_invocations_v.confirmation_id%type,
    p_confirmation_status  in  orac_api.plugin_invocations_v.confirmation_status%type,
    p_event_message        in  orac_api.plugin_audit_events_v.event_message%type default null,
    p_event_payload_json   in  orac_api.plugin_audit_events_v.event_payload_json%type default null,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type
  ) as
    l_row              orac_api.plugin_invocations_v%rowtype;
    l_execution_status orac_api.plugin_invocations_v.execution_status%type;
  begin
    orac_api.plugin_invocations_tapi.get(p_plugin_invocation_id, l_row);

    l_execution_status :=
      case p_event_type
        when 'confirmation_issued' then 'confirmation_issued'
        when 'confirmation_accepted' then 'confirmation_accepted'
        when 'confirmation_rejected' then 'confirmation_rejected'
        when 'confirmation_expired' then 'confirmation_expired'
        when 'confirmation_replay_rejected' then 'confirmation_replay_rejected'
        when 'confirmation_mismatched' then 'confirmation_mismatched'
        else l_row.execution_status
      end;

    l_row.confirmation_id := p_confirmation_id;
    l_row.confirmation_status := p_confirmation_status;
    l_row.execution_status := l_execution_status;

    orac_api.plugin_invocations_tapi.upd(p_plugin_invocation_id, l_row);
    p_row_version := l_row.row_version;

    add_event(
      p_plugin_invocation_id => p_plugin_invocation_id,
      p_event_type           => p_event_type,
      p_event_status         => p_confirmation_status,
      p_event_message        => p_event_message,
      p_policy_decision      => l_row.policy_decision,
      p_confirmation_id      => p_confirmation_id,
      p_execution_status     => l_execution_status,
      p_event_payload_json   => p_event_payload_json
    );
  end record_confirmation_event;

  procedure record_execution_event(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_event_type           in  orac_api.plugin_audit_events_v.event_type%type,
    p_execution_status     in  orac_api.plugin_invocations_v.execution_status%type,
    p_timeout_seconds      in  orac_api.plugin_invocations_v.timeout_seconds%type default null,
    p_failure_type         in  orac_api.plugin_invocations_v.failure_type%type default null,
    p_failure_message      in  orac_api.plugin_invocations_v.failure_message%type default null,
    p_provenance_json      in  orac_api.plugin_invocations_v.provenance_json%type default null,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type
  ) as
    l_row orac_api.plugin_invocations_v%rowtype;
  begin
    orac_api.plugin_invocations_tapi.get(p_plugin_invocation_id, l_row);

    l_row.execution_status := p_execution_status;
    l_row.timeout_seconds := p_timeout_seconds;
    l_row.failure_type := p_failure_type;
    l_row.failure_message := p_failure_message;

    -- Keep the invocation's original provenance and record this lifecycle
    -- snapshot on the event row. See record_policy_decision for the Oracle
    -- 23.26 JSON update restriction.

    orac_api.plugin_invocations_tapi.upd(p_plugin_invocation_id, l_row);
    p_row_version := l_row.row_version;

    add_event(
      p_plugin_invocation_id => p_plugin_invocation_id,
      p_event_type           => p_event_type,
      p_event_message        => p_failure_message,
      p_policy_decision      => l_row.policy_decision,
      p_confirmation_id      => l_row.confirmation_id,
      p_execution_status     => p_execution_status,
      p_failure_type         => p_failure_type,
      p_failure_message      => p_failure_message,
      p_event_payload_json   => p_provenance_json
    );
  end record_execution_event;

  procedure link_message(
    p_plugin_invocation_id in  orac_api.plugin_invocations_v.plugin_invocation_id%type,
    p_message_id           in  orac_api.plugin_invocations_v.message_id%type,
    p_row_version          out orac_api.plugin_invocations_v.row_version%type
  ) as
    l_row orac_api.plugin_invocations_v%rowtype;
  begin
    orac_api.plugin_invocations_tapi.get(p_plugin_invocation_id, l_row);
    l_row.message_id := p_message_id;

    orac_api.plugin_invocations_tapi.upd(p_plugin_invocation_id, l_row);
    p_row_version := l_row.row_version;
  end link_message;
end plugin_audit_api;
/
