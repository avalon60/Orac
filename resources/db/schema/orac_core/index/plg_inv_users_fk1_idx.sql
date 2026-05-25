-- __author__: clive
-- __date__: 2026-05-25
-- __description__: user foreign key index for plugin_invocations


create index orac_core.plg_inv_users_fk1_idx
  on orac_core.plugin_invocations
  (
    user_id asc
  )
;
