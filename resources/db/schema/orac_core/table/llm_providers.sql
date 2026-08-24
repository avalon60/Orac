--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines reviewed model-provider adapter metadata.

--changeset clive:create_table_orac_core_llm_providers context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'LLM_PROVIDERS';
create table orac_core.llm_providers
(
  provider_code                         varchar2(100 char) not null,
  display_name                          varchar2(200 char) not null,
  adapter_class                         varchar2(255 char) not null,
  processing_locality_domain_code       varchar2(100 char) default on null 'PROCESSING_LOCALITY' not null,
  processing_locality_ref_value_code    varchar2(100 char) not null,
  metadata_status_domain_code           varchar2(100 char) default on null 'PROVIDER_METADATA_STATUS' not null,
  metadata_status_ref_value_code        varchar2(100 char) not null,
  effective_from                        timestamp with local time zone default on null systimestamp not null,
  effective_to                          timestamp with local time zone,
  native_properties                     json,
  created_by                            varchar2(128 char) default on null coalesce(
                                          sys_context('apex$session', 'app_user'),
                                          sys_context('userenv', 'proxy_user'),
                                          sys_context('userenv', 'session_user'),
                                          user
                                        ) not null,
  created_on                            timestamp with local time zone default on null systimestamp not null,
  updated_by                            varchar2(128 char),
  updated_on                            timestamp with local time zone,
  row_version                           number default 1 not null
);
--rollback drop table orac_core.llm_providers purge;
