-- __author__: clive
-- __date__: 2026-05-25
-- __description__: conversation foreign key for plugin_invocations


alter table orac_core.plugin_invocations
  add constraint plg_inv_convs_fk1
  foreign key
  (
    conversation_id
  )
  references orac_core.conversations
  (
    conversation_id
  )
  on delete set null
;
