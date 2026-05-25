-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_invocations timeout seconds


alter table orac_core.plugin_invocations
  add constraint plg_inv_ck4
  check (timeout_seconds is null or timeout_seconds >= 0)
;
