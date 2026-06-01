-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key index for plugin_invocations


create unique index orac_core.plg_inv_pk
  on orac_core.plugin_invocations
  (
    plugin_invocation_id asc
  )
;
