--liquibase formatted sql
-- Author: clive
-- Date: 12-Sep-2026
-- Description: Durable removal authorization, checkpoints and outcome; never an installed-plugin inventory.

--changeset clive:create_table_orac_core_plugin_removals context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tables where owner = 'ORAC_CORE' and table_name = 'PLUGIN_REMOVALS';
create table orac_core.plugin_removals
(
  removal_id varchar2(32 char) not null,
  plugin_id varchar2(128 char) not null,
  plugin_registry_id number not null,
  knowledge_scope_id number not null,
  plugin_version varchar2(64 char) not null,
  manifest_hash varchar2(64 char) not null,
  schema_disposition varchar2(10 char) not null,
  database_identity varchar2(256 char) not null,
  resource_inventory json not null,
  checkpoints json,
  external_complete_yn varchar2(1 char) default 'N' not null,
  files_complete_yn varchar2(1 char) default 'N' not null,
  confirmed_by varchar2(128 char) not null,
  completed_on timestamp with time zone,
  last_error_code varchar2(128 char),
  last_error_message varchar2(2000 char),
  created_on timestamp default systimestamp not null,
  created_by varchar2(128 char) default sys_context('userenv', 'session_user') not null,
  updated_on timestamp,
  updated_by varchar2(128 char),
  row_version number default 1 not null
);
--rollback drop table orac_core.plugin_removals;
