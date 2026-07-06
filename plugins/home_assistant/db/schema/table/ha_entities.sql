--liquibase formatted sql

--changeset cbostock:home_assistant_table_ha_entities context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_HA' and table_name = 'HA_ENTITIES'
--------------------------------------------------------------------------------
-- ha_entities
--------------------------------------------------------------------------------
create table orac_ha.ha_entities (
  entity_id            varchar2(255 char) not null,
  ha_entity_id         varchar2(64 char) not null,
  unique_id            varchar2(255 char),
  platform             varchar2(64 char),
  device_id            varchar2(64 char),
  area_id              varchar2(64 char),
  config_entry_id      varchar2(64 char),
  config_subentry_id   varchar2(64 char),
  entity_category      varchar2(32 char),
  disabled_by          varchar2(32 char),
  hidden_by            varchar2(32 char),
  has_entity_name      varchar2(1 char),
  name                 varchar2(255 char),
  original_name        varchar2(255 char),
  translation_key      varchar2(255 char),
  icon                 varchar2(255 char),
  ha_created_at        timestamp with time zone,
  ha_modified_at       timestamp with time zone,
  options              clob,
  categories           clob,
  labels               clob,
  created_by           varchar2(128 char) default coalesce(
                         sys_context('apex$session', 'app_user'),
                         sys_context('userenv', 'proxy_user'),
                         sys_context('userenv', 'session_user'),
                         user
                       ) not null,
  created_on           timestamp with time zone default systimestamp not null,
  updated_by           varchar2(128 char) default coalesce(
                         sys_context('apex$session', 'app_user'),
                         sys_context('userenv', 'proxy_user'),
                         sys_context('userenv', 'session_user'),
                         user
                       ) not null,
  updated_on           timestamp with time zone default systimestamp not null,
  row_version          number default 1 not null
);

--rollback drop table orac_ha.ha_entities;
