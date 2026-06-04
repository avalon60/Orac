create or replace package orac_ha.ha_sync_api as

  function safe_ts(
    p_value in varchar2
  ) return timestamp with time zone;

  procedure begin_sync_run(
    p_sync_run_id in orac_ha.ha_sync_runs.sync_run_id%type,
    p_sync_type   in orac_ha.ha_sync_runs.sync_type%type
  );

  procedure complete_sync_run(
    p_sync_run_id    in orac_ha.ha_sync_runs.sync_run_id%type,
    p_rows_processed in orac_ha.ha_sync_runs.rows_processed%type,
    p_message        in orac_ha.ha_sync_runs.message%type default null
  );

  procedure fail_sync_run(
    p_sync_run_id   in orac_ha.ha_sync_runs.sync_run_id%type,
    p_error_message in orac_ha.ha_sync_runs.error_message%type
  );

  procedure merge_area(
    p_payload in clob
  );

  procedure merge_device(
    p_payload in clob
  );

  procedure merge_entity(
    p_payload in clob
  );

  procedure merge_state(
    p_payload in clob
  );

end ha_sync_api;
/
