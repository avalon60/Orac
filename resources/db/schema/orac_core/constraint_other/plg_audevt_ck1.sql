-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_audit_events event type


alter table orac_core.plugin_audit_events
  add constraint plg_audevt_ck1
  check (
    event_type in (
      'candidate_selected',
      'policy_evaluated',
      'confirmation_required',
      'confirmation_issued',
      'confirmation_accepted',
      'confirmation_rejected',
      'confirmation_expired',
      'confirmation_replay_rejected',
      'confirmation_mismatched',
      'execution_started',
      'execution_completed',
      'execution_failed',
      'execution_timed_out'
    )
  )
;
