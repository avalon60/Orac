comment on table orac_core.plugin_audit_events is
  'Append-only plugin audit lifecycle event stream linked to plugin invocation summaries.'
;

comment on column orac_core.plugin_audit_events.plugin_audit_event_id is
  'Primary key for plugin audit lifecycle events.'
;

comment on column orac_core.plugin_audit_events.plugin_invocation_id is
  'Plugin invocation summary row associated with this event.'
;

comment on column orac_core.plugin_audit_events.event_type is
  'Lifecycle event type recorded by Orac core.'
;

comment on column orac_core.plugin_audit_events.event_status is
  'Event-local status when distinct from execution status.'
;

comment on column orac_core.plugin_audit_events.event_message is
  'Safe event message, not a raw exception or stack trace.'
;

comment on column orac_core.plugin_audit_events.policy_decision is
  'Policy decision associated with this event when applicable.'
;

comment on column orac_core.plugin_audit_events.confirmation_id is
  'Trusted confirmation broker identifier associated with this event.'
;

comment on column orac_core.plugin_audit_events.execution_status is
  'Invocation execution status associated with this event when applicable.'
;

comment on column orac_core.plugin_audit_events.failure_type is
  'Safe failure category associated with this event.'
;

comment on column orac_core.plugin_audit_events.failure_message is
  'Safe failure summary associated with this event.'
;

comment on column orac_core.plugin_audit_events.event_payload_json is
  'Structured event payload or provenance snapshot for forward compatibility.'
;
