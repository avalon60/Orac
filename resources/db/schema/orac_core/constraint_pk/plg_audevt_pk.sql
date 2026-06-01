-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key for plugin_audit_events


alter table orac_core.plugin_audit_events
  add constraint plg_audevt_pk
  primary key (plugin_audit_event_id)
;
