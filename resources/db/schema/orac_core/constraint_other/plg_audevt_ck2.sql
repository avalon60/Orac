-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_audit_events policy decision


alter table orac_core.plugin_audit_events
  add constraint plg_audevt_ck2
  check (
    policy_decision is null
    or policy_decision in ('allowed', 'denied', 'requires_confirmation')
  )
;
