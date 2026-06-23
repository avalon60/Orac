-- orac-expected-columns: plugin_id, service_running, api_reachable
-- orac-expected-columns: last_startup_sync_at, last_startup_sync_status
-- orac-expected-columns: last_state_sync_at, last_state_sync_status
-- orac-expected-columns: last_areas_processed, last_devices_processed
-- orac-expected-columns: last_entities_processed, last_states_processed
-- orac-expected-columns: last_error_message_redacted, updated_at
create or replace view orac_ha.ha_status_summary_v as
with latest_runs as (
  select sync_type,
         status,
         rows_processed,
         error_message,
         coalesce(completed_on, started_on) sync_at,
         updated_on,
         row_number() over (
           partition by sync_type
               order by coalesce(completed_on, started_on) desc,
                        updated_on desc,
                        sync_run_id desc
         ) rn
    from orac_ha.ha_sync_runs
),
latest_error as (
  select error_message,
         row_number() over (
           order by coalesce(completed_on, started_on) desc,
                    updated_on desc,
                    sync_run_id desc
         ) rn
    from orac_ha.ha_sync_runs
   where error_message is not null
),
redacted_error as (
  select regexp_replace(
           regexp_replace(
             regexp_replace(
               regexp_replace(
                 error_message,
                 '("?(access[_-]?token|token|password|passwd|secret|api[_-]?key)"?[[:space:]]*:[[:space:]]*")[^"]+(")',
                 '\1[redacted]\3',
                 1,
                 0,
                 'i'
               ),
               '([[:alpha:]][[:alnum:]+.-]*://)[^/@[:space:]:]+:[^/@[:space:]]+@',
               '\1[redacted]@',
               1,
               0,
               'i'
             ),
             '(bearer)[[:space:]]+[[:alnum:]_.~+/=-]+',
             '\1 [redacted]',
             1,
             0,
             'i'
           ),
           '((access[_-]?token|token|password|passwd|secret|api[_-]?key)[[:space:]]*[:=][[:space:]]*)[^[:space:],;]+',
           '\1[redacted]',
           1,
           0,
           'i'
         ) error_message_redacted
    from latest_error
   where rn = 1
)
select 'home_assistant' plugin_id,
       cast(null as varchar2(5 char)) service_running,
       cast(null as varchar2(5 char)) api_reachable,
       structural.sync_at last_startup_sync_at,
       structural.status last_startup_sync_status,
       state_sync.sync_at last_state_sync_at,
       state_sync.status last_state_sync_status,
       (select count(*) from orac_ha.ha_areas) last_areas_processed,
       (select count(*) from orac_ha.ha_devices) last_devices_processed,
       (select count(*) from orac_ha.ha_entities) last_entities_processed,
       (select count(*) from orac_ha.ha_states_current) last_states_processed,
       redacted_error.error_message_redacted last_error_message_redacted,
       coalesce(
         (select max(updated_on) from orac_ha.ha_sync_runs),
         systimestamp
       ) updated_at
  from dual
  left join latest_runs structural
    on structural.sync_type = 'structural'
   and structural.rn = 1
  left join latest_runs state_sync
    on state_sync.sync_type = 'state'
   and state_sync.rn = 1
  left join redacted_error
    on 1 = 1
;
