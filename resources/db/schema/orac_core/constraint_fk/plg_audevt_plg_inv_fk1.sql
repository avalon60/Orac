-- __author__: clive
-- __date__: 2026-05-25
-- __description__: plugin invocation foreign key for plugin_audit_events


alter table orac_core.plugin_audit_events
  add constraint plg_audevt_plg_inv_fk1
  foreign key
  (
    plugin_invocation_id
  )
  references orac_core.plugin_invocations
  (
    plugin_invocation_id
  )
;
