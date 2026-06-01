comment on table orac_core.plugin_invocations is
  'One summary row per Orac-owned plugin invocation attempt or policy-stopped plugin action.'
;

comment on column orac_core.plugin_invocations.plugin_invocation_id is
  'Primary key for plugin invocation audit summaries.'
;

comment on column orac_core.plugin_invocations.request_id is
  'Protocol request identifier when available.'
;

comment on column orac_core.plugin_invocations.correlation_id is
  'Cross-component correlation identifier when available.'
;

comment on column orac_core.plugin_invocations.turn_id is
  'Voice or display turn identifier when available.'
;

comment on column orac_core.plugin_invocations.conversation_id is
  'Optional conversation linked to the plugin decision or result.'
;

comment on column orac_core.plugin_invocations.message_id is
  'Optional message linked to the plugin decision or result.'
;

comment on column orac_core.plugin_invocations.user_id is
  'Optional Orac user linked to the plugin decision or result.'
;

comment on column orac_core.plugin_invocations.plugin_id is
  'Stable plugin identifier from the plugin manifest.'
;

comment on column orac_core.plugin_invocations.plugin_name is
  'Plugin display name captured at invocation time.'
;

comment on column orac_core.plugin_invocations.action_type is
  'Execution policy action type evaluated by Orac core.'
;

comment on column orac_core.plugin_invocations.capabilities is
  'JSON array or object of plugin capabilities considered during policy evaluation.'
;

comment on column orac_core.plugin_invocations.entitlements is
  'JSON array or object of entitlements considered during policy evaluation.'
;

comment on column orac_core.plugin_invocations.policy_decision is
  'Policy decision: allowed, denied, or requires_confirmation.'
;

comment on column orac_core.plugin_invocations.policy_reason is
  'Safe policy reason text, not a raw exception or stack trace.'
;

comment on column orac_core.plugin_invocations.confirmation_id is
  'Trusted confirmation broker identifier when confirmation is involved.'
;

comment on column orac_core.plugin_invocations.confirmation_status is
  'Trusted confirmation status recorded by Orac core.'
;

comment on column orac_core.plugin_invocations.execution_status is
  'Current or final plugin invocation lifecycle status.'
;

comment on column orac_core.plugin_invocations.timeout_seconds is
  'Configured plugin execution timeout when relevant.'
;

comment on column orac_core.plugin_invocations.failure_type is
  'Safe plugin failure category.'
;

comment on column orac_core.plugin_invocations.failure_message is
  'Safe plugin failure summary suitable for audit display.'
;

comment on column orac_core.plugin_invocations.provenance_json is
  'Orac-owned plugin provenance snapshot.'
;
