-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key index for plugin_audit_events


create unique index orac_core.plg_audevt_pk
  on orac_core.plugin_audit_events
  (
    plugin_audit_event_id asc
  )
;
