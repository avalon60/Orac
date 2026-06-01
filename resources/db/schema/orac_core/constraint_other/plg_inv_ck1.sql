-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_invocations policy decision


alter table orac_core.plugin_invocations
  add constraint plg_inv_ck1
  check (
    policy_decision is null
    or policy_decision in ('allowed', 'denied', 'requires_confirmation')
  )
;
