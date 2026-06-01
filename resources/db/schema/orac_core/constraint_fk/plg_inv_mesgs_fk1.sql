-- __author__: clive
-- __date__: 2026-05-25
-- __description__: message foreign key for plugin_invocations


alter table orac_core.plugin_invocations
  add constraint plg_inv_mesgs_fk1
  foreign key
  (
    message_id
  )
  references orac_core.messages
  (
    message_id
  )
  on delete set null
;
