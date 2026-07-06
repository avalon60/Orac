--liquibase formatted sql

--changeset cbostock:home_assistant_table_ha_devices context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_HA' and table_name = 'HA_DEVICES'
create table orac_ha.ha_devices
(
  device_id                 varchar2(64 char) not null,
  name                      varchar2(255 char),
  name_by_user              varchar2(255 char),
  manufacturer              varchar2(255 char),
  model                     varchar2(255 char),
  model_id                  varchar2(255 char),
  area_id                   varchar2(64 char),
  via_device_id             varchar2(64 char),
  hw_version                varchar2(255 char),
  sw_version                varchar2(255 char),
  serial_number             varchar2(255 char),
  entry_type                varchar2(64 char),
  disabled_by               varchar2(64 char),
  primary_config_entry      varchar2(64 char),
  configuration_url         varchar2(1024 char),
  connections               clob,
  identifiers               clob,
  config_entries            clob,
  config_entries_subentries clob,
  labels                    clob,
  ha_created_at             timestamp with time zone,
  ha_modified_at            timestamp with time zone,
  created_by                varchar2(128 char) default coalesce(
                              sys_context('apex$session', 'app_user'),
                              sys_context('userenv', 'proxy_user'),
                              sys_context('userenv', 'session_user'),
                              user
                            ) not null,
  created_on                timestamp with time zone default systimestamp not null,
  updated_by                varchar2(128 char) default coalesce(
                              sys_context('apex$session', 'app_user'),
                              sys_context('userenv', 'proxy_user'),
                              sys_context('userenv', 'session_user'),
                              user
                            ) not null,
  updated_on                timestamp with time zone default systimestamp not null,
  row_version               number default 1 not null
)
logging
no inmemory
lob (connections) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
)
lob (identifiers) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
)
lob (config_entries) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
)
lob (config_entries_subentries) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
)
lob (labels) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
);

--rollback drop table orac_ha.ha_devices;
