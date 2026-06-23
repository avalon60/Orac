--liquibase formatted sql

--changeset clive:create_table_orac_core_table_llm_registry context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'LLM_REGISTRY';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create table orac_core.llm_registry
(
  llm_id             number generated always as identity not null,
  name               varchar2(100 byte) not null,
  provider           varchar2(100 byte),
  model              varchar2(200 byte) not null,
  context_policy     varchar2(20 byte) not null,
  max_context_tokens number,
  is_enabled         char(1 byte) default 'Y' not null,
  properties         json,
  created_on         timestamp default on null systimestamp not null,
  created_by         varchar2(128 byte) default on null coalesce(
                       sys_context('apex$session', 'app_user'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     ) not null,
  updated_on         timestamp,
  updated_by         varchar2(128 byte),
  row_version        number default 1 not null
)
;

--rollback drop table orac_core.llm_registry purge;
