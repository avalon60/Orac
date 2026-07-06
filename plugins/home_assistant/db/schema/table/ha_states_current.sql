--liquibase formatted sql

--changeset cbostock:home_assistant_table_ha_states_current context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_HA' and table_name = 'HA_STATES_CURRENT'
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create table orac_ha.ha_states_current
(
  entity_id         varchar2(255 char) not null,
  state             varchar2(255 char),
  attributes        clob,
  last_changed      timestamp with time zone,
  last_updated      timestamp with time zone,
  last_reported     timestamp with time zone,
  context_id        varchar2(64 char),
  context_parent_id varchar2(64 char),
  context_user_id   varchar2(64 char),
  created_by        varchar2(128 char) default coalesce(
                      sys_context('apex$session', 'app_user'),
                      sys_context('userenv', 'proxy_user'),
                      sys_context('userenv', 'session_user'),
                      user
                    ) not null,
  created_on        timestamp with time zone default systimestamp not null,
  updated_by        varchar2(128 char) default coalesce(
                      sys_context('apex$session', 'app_user'),
                      sys_context('userenv', 'proxy_user'),
                      sys_context('userenv', 'session_user'),
                      user
                    ) not null,
  updated_on        timestamp with time zone default systimestamp not null,
  row_version       number default 1 not null
)
logging
no inmemory
lob (attributes) store as securefile
(
  chunk 8192
  retention
  enable storage in row
  nocache logging
);

--rollback drop table orac_ha.ha_states_current;
