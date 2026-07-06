--liquibase formatted sql

--changeset cbostock:home_assistant_table_ha_sync_runs context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_HA' and table_name = 'HA_SYNC_RUNS'
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
  created_by     varchar2(128 char) default coalesce(
                   sys_context('apex$session', 'app_user'),
                   sys_context('userenv', 'proxy_user'),
                   sys_context('userenv', 'session_user'),
                   user
                 ) not null,
  created_on     timestamp with time zone default systimestamp not null,
  updated_by     varchar2(128 char) default coalesce(
                   sys_context('apex$session', 'app_user'),
                   sys_context('userenv', 'proxy_user'),
                   sys_context('userenv', 'session_user'),
                   user
                 ) not null,
  updated_on     timestamp with time zone default systimestamp not null,
  row_version    number default 1 not null
)
logging
no inmemory;

--rollback drop table orac_ha.ha_sync_runs;
