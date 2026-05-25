-- __author__: clive
-- __date__: 2026-05-25
-- __description__: plugin invocation foreign key index for plugin_audit_events


create index orac_core.plg_audevt_plg_inv_fk1_idx
  on orac_core.plugin_audit_events
  (
    plugin_invocation_id asc
  )
;
