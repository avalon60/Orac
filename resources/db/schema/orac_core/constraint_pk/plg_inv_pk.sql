-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key for plugin_invocations


alter table orac_core.plugin_invocations
  add constraint plg_inv_pk
  primary key (plugin_invocation_id)
;
