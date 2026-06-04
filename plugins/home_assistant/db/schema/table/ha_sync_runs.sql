create table orac_ha.ha_sync_runs
(
  sync_run_id    varchar2(36 char) not null,
  sync_type      varchar2(32 char) not null,
  status         varchar2(32 char) not null,
  rows_processed number default 0 not null,
  message        varchar2(4000 char),
  error_message  varchar2(4000 char),
  started_on     timestamp with time zone not null,
  completed_on   timestamp with time zone,
  row_version    number not null,
  created_on     timestamp with time zone not null,
  updated_on     timestamp with time zone not null
)
logging
no inmemory
;
