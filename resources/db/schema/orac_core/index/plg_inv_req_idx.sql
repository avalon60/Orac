-- __author__: clive
-- __date__: 2026-05-25
-- __description__: request correlation index for plugin_invocations


create index orac_core.plg_inv_req_idx
  on orac_core.plugin_invocations
  (
    request_id asc,
    correlation_id asc,
    turn_id asc
  )
;
