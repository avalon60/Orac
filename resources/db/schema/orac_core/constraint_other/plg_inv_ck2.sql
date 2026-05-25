-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_invocations confirmation status


alter table orac_core.plugin_invocations
  add constraint plg_inv_ck2
  check (
    confirmation_status is null
    or confirmation_status in (
      'issued',
      'accepted',
      'rejected',
      'expired',
      'replayed',
      'replay_rejected',
      'mismatched',
      'missing',
      'pending'
    )
  )
;
