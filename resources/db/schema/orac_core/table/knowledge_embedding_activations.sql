--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Selects the active immutable embedding profile for each purpose.

--changeset clive:create_table_orac_core_knowledge_embedding_activations context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'KNOWLEDGE_EMBEDDING_ACTIVATIONS';
create table orac_core.knowledge_embedding_activations
(
  purpose_code          varchar2(100 char) not null,
  embedding_profile_id  number not null,
  activated_by          varchar2(128 char) default coalesce(
                          sys_context('apex$session', 'app_user'),
                          sys_context('userenv', 'proxy_user'),
                          sys_context('userenv', 'session_user'),
                          user
                        ) not null,
  activated_on          timestamp with time zone default systimestamp not null,
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
no inmemory;
--rollback drop table orac_core.knowledge_embedding_activations purge;
