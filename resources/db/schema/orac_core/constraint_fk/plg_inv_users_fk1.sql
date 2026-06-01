-- __author__: clive
-- __date__: 2026-05-25
-- __description__: user foreign key for plugin_invocations


alter table orac_core.plugin_invocations
  add constraint plg_inv_users_fk1
  foreign key
  (
    user_id
  )
  references orac_core.users
  (
    user_id
  )
  on delete set null
;
