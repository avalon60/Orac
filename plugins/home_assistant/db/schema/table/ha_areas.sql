--liquibase formatted sql

--changeset cbostock:home_assistant_table_ha_areas context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_HA' and table_name = 'HA_AREAS'
create table orac_ha.ha_areas
(
  area_id               varchar2(64 char) not null,
  name                  varchar2(255 char) not null,
  floor_id              varchar2(64 char),
  icon                  varchar2(255 char),
  picture               varchar2(255 char),
  humidity_entity_id    varchar2(255 char),
  temperature_entity_id varchar2(255 char),
  aliases               clob,
  labels                clob,
  ha_created_at         timestamp with time zone,
  ha_modified_at        timestamp with time zone,
  created_by            varchar2(128 char) default coalesce(
                          sys_context('apex$session', 'app_user'),
                          sys_context('userenv', 'proxy_user'),
                          sys_context('userenv', 'session_user'),
                          user
                        ) not null,
  created_on            timestamp with time zone default systimestamp not null,
  updated_by            varchar2(128 char) default coalesce(
                          sys_context('apex$session', 'app_user'),
                          sys_context('userenv', 'proxy_user'),
                          sys_context('userenv', 'session_user'),
                          user
                        ) not null,
  updated_on            timestamp with time zone default systimestamp not null,
  row_version           number default 1 not null
)
logging
no inmemory
lob (aliases) store as securefile
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

--rollback drop table orac_ha.ha_areas;
